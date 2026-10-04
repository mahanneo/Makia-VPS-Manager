#!/usr/bin/env python3
from pathlib import Path
import re, sys

root=Path(sys.argv[1]).resolve()
overlay=Path(sys.argv[2]).resolve()
MAKIA_VERSION_NAME="1.5.1"
MAKIA_VERSION_CODE="10501"

version_props=root/"version.properties"
vp=version_props.read_text(encoding="utf-8")
vp=re.sub(r"(?m)^VERSION_NAME=.*$",f"VERSION_NAME={MAKIA_VERSION_NAME}",vp)
vp=re.sub(r"(?m)^VERSION_CODE=.*$",f"VERSION_CODE={MAKIA_VERSION_CODE}",vp)
version_props.write_text(vp,encoding="utf-8")

build=root/"app/build.gradle.kts"
s=build.read_text(encoding="utf-8")
s=s.replace('applicationId = "io.nekohasekai.sfa"','applicationId = "com.makia.client"')
s=s.replace('base.archivesName.set("SFA-${versionName}")','base.archivesName.set("Makia-Android-Connector-${versionName}")')
build.write_text(s,encoding="utf-8")

dst=root/"app/src/main/java/io/nekohasekai/sfa/makia/MakiaEntryActivity.kt"
dst.parent.mkdir(parents=True,exist_ok=True)
dst.write_text(overlay.read_text(encoding="utf-8"),encoding="utf-8")

manifest=root/"app/src/main/AndroidManifest.xml"
m=manifest.read_text(encoding="utf-8")
launcher='''<intent-filter>
                <action android:name="android.intent.action.MAIN" />

                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>'''
m=m.replace(launcher,"",1)
activity='''        <activity
            android:name=".makia.MakiaEntryActivity"
            android:exported="true"
            android:launchMode="singleTask"
            android:theme="@style/AppTheme">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
            <intent-filter>
                <action android:name="android.intent.action.VIEW" />
                <category android:name="android.intent.category.DEFAULT" />
                <category android:name="android.intent.category.BROWSABLE" />
                <data android:scheme="makia" android:host="connect" />
                <data android:scheme="makia" android:host="disconnect" />
            </intent-filter>
        </activity>
'''
needle="        <activity\n            android:name=\".compose.MainActivity\""
if needle not in m:
    raise SystemExit("MainActivity manifest marker missing")
m=m.replace(needle,activity+needle,1)
manifest.write_text(m,encoding="utf-8")

changed=0
for p in (root/"app/src/main/res").glob("values*/strings.xml"):
    text=p.read_text(encoding="utf-8")
    new=re.sub(r'(<string name="app_name">)(.*?)(</string>)',r'\1Makia Connector\3',text,count=1)
    if new!=text:
        p.write_text(new,encoding="utf-8");changed+=1
if not changed:
    print("WARN: app_name was not found in strings.xml",file=sys.stderr)

print("Makia Android overlay applied")
