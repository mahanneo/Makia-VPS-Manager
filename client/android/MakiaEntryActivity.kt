/*
 * Makia Android Connector overlay.
 * This file is part of the Android connector derivative and is licensed GPL-3.0-or-later.
 */
package io.nekohasekai.sfa.makia

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.net.VpnService
import android.os.Bundle
import android.os.Build
import android.util.Base64
import android.widget.TextView
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.lifecycle.lifecycleScope
import io.nekohasekai.libbox.Libbox
import io.nekohasekai.sfa.BuildConfig
import io.nekohasekai.sfa.bg.BoxService
import io.nekohasekai.sfa.database.Profile
import io.nekohasekai.sfa.database.ProfileManager
import io.nekohasekai.sfa.database.Settings
import io.nekohasekai.sfa.database.TypedProfile
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

class MakiaEntryActivity : ComponentActivity() {
    companion object {
        private const val VPN_REQUEST = 7001
        private var wstunnelProcess: Process? = null
    }

    private var startAfterPermission = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val view = TextView(this).apply {
            text = "Makia Connector\n\nاتصال از داخل Makia Web App کنترل می‌شود."
            textSize = 18f
            setPadding(48, 80, 48, 48)
        }
        setContentView(view)
        handle(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handle(intent)
    }

    private fun handle(intent: Intent?) {
        val uri = intent?.data ?: return
        if (uri.scheme != "makia") return
        when (uri.host) {
            "disconnect" -> {
                BoxService.stop()
                stopWstunnel()
                Toast.makeText(this, "اتصال Makia قطع شد", Toast.LENGTH_SHORT).show()
                finish()
            }
            "connect" -> connect(uri)
        }
    }

    private fun connect(uri: Uri) {
        val controller = uri.getQueryParameter("controller") ?: return fail("Controller missing")
        val ticket = uri.getQueryParameter("ticket") ?: return fail("Ticket missing")
        if (!controller.startsWith("https://") &&
            !(BuildConfig.DEBUG && (controller.startsWith("http://127.0.0.1") || controller.startsWith("http://localhost")))
        ) return fail("HTTPS required")

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val delivery = redeem(controller, ticket)
                val config = buildConfig(delivery)
                Libbox.checkConfig(config)
                importProfile(config)
                Settings.rebuildServiceMode()
                withContext(Dispatchers.Main) { requestVpnAndStart() }
            } catch (e: Exception) {
                stopWstunnel()
                withContext(Dispatchers.Main) { fail(e.message ?: "اتصال ناموفق بود") }
            }
        }
    }

    private fun redeem(controller: String, ticket: String): JSONObject {
        val connection = URL(controller.trimEnd('/') + "/client/connector/redeem").openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.connectTimeout = 15000
        connection.readTimeout = 15000
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "application/json")
        connection.setRequestProperty("User-Agent", "MakiaAndroidConnector/1.6.4")
        val body = JSONObject().put("ticket", ticket).toString().toByteArray()
        connection.outputStream.use { it.write(body) }
        val code = connection.responseCode
        val stream = if (code in 200..299) connection.inputStream else connection.errorStream
        val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
        if (code !in 200..299) throw IllegalStateException(JSONObject(text.ifBlank { "{}" }).optString("detail", "ticket rejected"))
        return JSONObject(text)
    }

    private suspend fun importProfile(config: String) {
        val typed = TypedProfile().apply { type = TypedProfile.Type.Local }
        val profile = Profile(name = "Makia Direct", typed = typed).apply {
            userOrder = ProfileManager.nextOrder()
        }
        val fileId = ProfileManager.nextFileID()
        val dir = File(filesDir, "configs").also { it.mkdirs() }
        val file = File(dir, "$fileId.json")
        file.writeText(config)
        typed.path = file.path
        ProfileManager.create(profile, andSelect = true)
    }

    private fun requestVpnAndStart() {
        val prepare = VpnService.prepare(this)
        if (prepare != null) {
            startAfterPermission = true
            startActivityForResult(prepare, VPN_REQUEST)
        } else {
            startVpn()
        }
    }

    @Deprecated("VpnService permission callback")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == VPN_REQUEST) {
            if (resultCode == Activity.RESULT_OK && startAfterPermission) startVpn()
            else fail("مجوز VPN داده نشد")
        }
    }

    private fun startVpn() {
        startAfterPermission = false
        BoxService.start()
        Toast.makeText(this, "در حال برقراری اتصال Makia…", Toast.LENGTH_SHORT).show()
        finish()
    }

    private fun fail(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_LONG).show()
    }

    private fun buildConfig(d: JSONObject): String {
        val engine = d.optString("engine").lowercase()
        val share = d.optString("share_link")
        val root = JSONObject()
        root.put("log", JSONObject().put("level", "info"))
        val tun = JSONObject().put("type", "tun").put("tag", "tun-in")
            .put("address", JSONArray().put("172.19.0.1/30"))
            .put("mtu", 1400).put("auto_route", true).put("strict_route", true)
        if (engine == "wstunnel_wireguard") tun.put("exclude_package", JSONArray().put(packageName))
        root.put("inbounds", JSONArray().put(tun))

        if (engine == "wstunnel_wireguard") {
            val raw = String(Base64.decode(d.getString("native_base64"), Base64.DEFAULT))
            startWstunnel(d.getJSONObject("transport_config"))
            root.put("endpoints", JSONArray().put(parseWireGuard(raw)))
            root.put("outbounds", JSONArray().put(JSONObject().put("type", "direct").put("tag", "direct")))
            root.put("route", JSONObject().put("final", "wg-ep"))
        } else if (engine == "wireguard") {
            val raw = if (d.optString("native_base64").isNotBlank()) {
                String(Base64.decode(d.getString("native_base64"), Base64.DEFAULT))
            } else share
            root.put("endpoints", JSONArray().put(parseWireGuard(raw)))
            root.put("outbounds", JSONArray().put(JSONObject().put("type", "direct").put("tag", "direct")))
            root.put("route", JSONObject().put("final", "wg-ep"))
        } else {
            root.put("outbounds", JSONArray()
                .put(parseOutbound(share))
                .put(JSONObject().put("type", "direct").put("tag", "direct")))
            root.put("route", JSONObject().put("final", "proxy"))
        }
        return root.toString()
    }

    private fun stopWstunnel() {
        try {
            wstunnelProcess?.destroy()
            Thread.sleep(100)
            if (wstunnelProcess?.isAlive == true) wstunnelProcess?.destroyForcibly()
        } catch (_: Exception) {
        } finally {
            wstunnelProcess = null
        }
    }

    private fun startWstunnel(cfg: JSONObject) {
        stopWstunnel()
        if (!Build.SUPPORTED_ABIS.contains("arm64-v8a")) throw IllegalStateException("WStunnel 443 فعلاً روی گوشی‌های ARM64 پشتیبانی می‌شود")
        if (cfg.optString("type") != "wireguard-wstunnel") throw IllegalArgumentException("Invalid WStunnel transport")
        val server=cfg.optString("server").trim()
        val port=cfg.optInt("port",0)
        val prefix=cfg.optString("path_prefix").trim()
        val localPort=cfg.optInt("local_port",0)
        val remoteHost=cfg.optString("remote_host").trim()
        val remotePort=cfg.optInt("remote_port",0)
        if (!Regex("^[A-Za-z0-9.-]{1,253}$").matches(server)) throw IllegalArgumentException("Invalid WStunnel server")
        if (port != 443) throw IllegalArgumentException("WStunnel public port must be 443")
        if (!Regex("^[A-Za-z0-9_-]{16,96}$").matches(prefix)) throw IllegalArgumentException("Invalid WStunnel path")
        if (localPort !in 1024..65535 || remotePort !in 1..65535) throw IllegalArgumentException("Invalid WStunnel port")
        if (remoteHost != "127.0.0.1") throw IllegalArgumentException("Invalid WStunnel target")
        val binary=File(applicationInfo.nativeLibraryDir,"libwstunnel.so")
        if (!binary.isFile || !binary.canExecute()) throw IllegalStateException("WStunnel runtime در برنامه پیدا نشد")
        val args=listOf(binary.absolutePath,"client","--http-upgrade-path-prefix",prefix,"--tls-verify-certificate",
            "-L","udp://127.0.0.1:$localPort:127.0.0.1:$remotePort?timeout_sec=0","wss://$server:443")
        val process=ProcessBuilder(args).redirectErrorStream(true)
            .redirectOutput(ProcessBuilder.Redirect.appendTo(File(filesDir,"wstunnel.log"))).start()
        Thread.sleep(900)
        if (!process.isAlive) throw IllegalStateException("WStunnel اجرا نشد")
        wstunnelProcess=process
    }

    private fun parseOutbound(value: String): JSONObject {
        val uri = Uri.parse(value)
        return when (uri.scheme?.lowercase()) {
            "vless" -> parseVlessTrojan(uri, "vless")
            "trojan" -> parseVlessTrojan(uri, "trojan")
            "hysteria2", "hy2" -> parseHy2(uri)
            "vmess" -> parseVmess(value)
            "ss" -> parseShadowsocks(value)
            "npvt-ssh" -> parseSsh(value)
            else -> throw IllegalArgumentException("این پروتکل هنوز Direct Connect اندروید ندارد")
        }
    }

    private fun parseVlessTrojan(uri: Uri, type: String): JSONObject {
        val out = JSONObject().put("type", type).put("tag", "proxy")
            .put("server", uri.host).put("server_port", if (uri.port > 0) uri.port else 443)
        val user = Uri.decode(uri.userInfo ?: "")
        if (type == "vless") out.put("uuid", user) else out.put("password", user)
        val security = uri.getQueryParameter("security") ?: ""
        if (security == "tls" || security == "reality") {
            val tls = JSONObject().put("enabled", true)
                .put("server_name", uri.getQueryParameter("sni") ?: uri.host)
            uri.getQueryParameter("fp")?.takeIf { it.isNotBlank() }?.let {
                tls.put("utls", JSONObject().put("enabled", true).put("fingerprint", it))
            }
            if (security == "reality") {
                tls.put("reality", JSONObject().put("enabled", true)
                    .put("public_key", uri.getQueryParameter("pbk") ?: "")
                    .put("short_id", uri.getQueryParameter("sid") ?: ""))
            }
            out.put("tls", tls)
        }
        uri.getQueryParameter("flow")?.takeIf { it.isNotBlank() }?.let { out.put("flow", it) }
        transport(uri)?.let { out.put("transport", it) }
        return out
    }

    private fun transport(uri: Uri): JSONObject? {
        return when (uri.getQueryParameter("type")?.lowercase()) {
            "ws" -> JSONObject().put("type", "ws")
                .put("path", uri.getQueryParameter("path") ?: "/")
                .apply {
                    uri.getQueryParameter("host")?.takeIf { it.isNotBlank() }?.let {
                        put("headers", JSONObject().put("Host", it))
                    }
                }
            "grpc" -> JSONObject().put("type", "grpc")
                .put("service_name", uri.getQueryParameter("serviceName") ?: uri.getQueryParameter("service_name") ?: "")
            "httpupgrade" -> JSONObject().put("type", "httpupgrade")
                .put("path", uri.getQueryParameter("path") ?: "/")
                .put("host", uri.getQueryParameter("host") ?: "")
            "http", "h2" -> JSONObject().put("type", "http")
                .put("path", uri.getQueryParameter("path") ?: "/")
            else -> null
        }
    }

    private fun parseHy2(uri: Uri): JSONObject {
        val out = JSONObject().put("type", "hysteria2").put("tag", "proxy")
            .put("server", uri.host).put("server_port", if (uri.port > 0) uri.port else 443)
            .put("password", Uri.decode(uri.userInfo ?: ""))
        val tls = JSONObject().put("enabled", true)
            .put("server_name", uri.getQueryParameter("sni") ?: uri.host)
            .put("insecure", uri.getQueryParameter("insecure") in listOf("1", "true"))
        out.put("tls", tls)
        uri.getQueryParameter("obfs")?.takeIf { it.isNotBlank() }?.let {
            out.put("obfs", JSONObject().put("type", it)
                .put("password", uri.getQueryParameter("obfs-password") ?: uri.getQueryParameter("obfs_password") ?: ""))
        }
        return out
    }

    private fun decodeLoose(raw: String): String {
        var value = raw
        while (value.length % 4 != 0) value += "="
        return String(Base64.decode(value, Base64.URL_SAFE or Base64.NO_WRAP))
    }

    private fun parseVmess(value: String): JSONObject {
        val obj = JSONObject(decodeLoose(value.substringAfter("://")))
        val out = JSONObject().put("type", "vmess").put("tag", "proxy")
            .put("server", obj.getString("add")).put("server_port", obj.optString("port", "443").toInt())
            .put("uuid", obj.getString("id")).put("security", obj.optString("scy", "auto"))
            .put("alter_id", obj.optString("aid", "0").toInt())
        if (obj.optString("tls").isNotBlank()) {
            out.put("tls", JSONObject().put("enabled", true)
                .put("server_name", obj.optString("sni", obj.optString("host", obj.getString("add")))))
        }
        if (obj.optString("net").isNotBlank()) {
            val fake = Uri.parse("vless://x@x?type=" + Uri.encode(obj.optString("net")) +
                "&path=" + Uri.encode(obj.optString("path")) + "&host=" + Uri.encode(obj.optString("host")))
            transport(fake)?.let { out.put("transport", it) }
        }
        return out
    }

    private fun parseShadowsocks(value: String): JSONObject {
        var raw = value.substringAfter("://").substringBefore("#")
        if (!raw.contains("@")) raw = decodeLoose(raw)
        val authPart = raw.substringBeforeLast("@")
        val serverPart = raw.substringAfterLast("@")
        val auth = if (authPart.contains(":")) authPart else decodeLoose(authPart)
        val method = auth.substringBefore(":")
        val password = auth.substringAfter(":")
        val host = serverPart.substringBeforeLast(":").removePrefix("[").removeSuffix("]")
        val port = serverPart.substringAfterLast(":").substringBefore("?").toInt()
        return JSONObject().put("type", "shadowsocks").put("tag", "proxy")
            .put("server", host).put("server_port", port)
            .put("method", method).put("password", Uri.decode(password))
    }

    private fun parseSsh(value: String): JSONObject {
        val obj = JSONObject(decodeLoose(value.substringAfter("://")))
        return JSONObject().put("type", "ssh").put("tag", "proxy")
            .put("server", obj.getString("sshHost")).put("server_port", obj.optInt("sshPort", 22))
            .put("user", obj.optString("sshUsername", "root")).put("password", obj.optString("sshPassword", ""))
    }

    private fun parseWireGuard(text: String): JSONObject {
        val iface = mutableMapOf<String, String>()
        val peer = mutableMapOf<String, String>()
        var current = ""
        text.lineSequence().forEach { raw ->
            val line = raw.substringBefore("#").trim()
            if (line.equals("[Interface]", true)) current = "interface"
            else if (line.equals("[Peer]", true)) current = "peer"
            else if (line.contains("=")) {
                val k = line.substringBefore("=").trim()
                val v = line.substringAfter("=").trim()
                if (current == "interface") iface[k] = v else if (current == "peer") peer[k] = v
            }
        }
        val endpoint = peer["Endpoint"] ?: throw IllegalArgumentException("WireGuard Endpoint missing")
        val host: String
        val port: Int
        if (endpoint.startsWith("[")) {
            host = endpoint.substringAfter("[").substringBefore("]")
            port = endpoint.substringAfter("]:").toInt()
        } else {
            host = endpoint.substringBeforeLast(":")
            port = endpoint.substringAfterLast(":").toInt()
        }
        return JSONObject().put("type", "wireguard").put("tag", "wg-ep")
            .put("system", false).put("mtu", iface["MTU"]?.toIntOrNull() ?: 1408)
            .put("address", JSONArray(iface["Address"]?.split(",")?.map { it.trim() } ?: emptyList<String>()))
            .put("private_key", iface["PrivateKey"] ?: "")
            .put("peers", JSONArray().put(JSONObject()
                .put("address", host).put("port", port)
                .put("public_key", peer["PublicKey"] ?: "")
                .put("pre_shared_key", peer["PresharedKey"] ?: "")
                .put("allowed_ips", JSONArray(peer["AllowedIPs"]?.split(",")?.map { it.trim() } ?: listOf("0.0.0.0/0")))
                .put("persistent_keepalive_interval", peer["PersistentKeepalive"]?.toIntOrNull() ?: 0)))
    }
}
