(() => {
  'use strict';
  const SPLAT_COUNT = 16;
  let renderer = null, scene = null, camera = null, points = null, frame = 0;
  let canvas = null, resizeHandler = null, pointerHandler = null, pointerDownHandler = null;
  let lastPointerAt = 0, clock = null, reducedMotion = false;
  let splats = [], splatUniforms = null, cameraTarget = null;
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  function makeGeometry(count) {
    const positions = new Float32Array(count * 3);
    const origins = new Float32Array(count * 3);
    const randoms = new Float32Array(count * 4);
    const tau = Math.PI * 2;
    for (let i = 0; i < count; i++) {
      const t = Math.random() * tau;
      const cross = Math.random() * tau;
      const tube = 0.035 + Math.pow(Math.random(), 0.46) * 0.125;
      const major = 0.405 + Math.sin(t * 3.0 + 0.3) * 0.032 + Math.sin(t * 5.0 - 0.7) * 0.018;
      const twist = t * 1.35 + 0.22 * Math.sin(t * 2.0);
      const r = major + tube * Math.cos(cross + twist * 0.2);
      const idx = i * 3;
      positions[idx] = r * Math.cos(t) + 0.018 * Math.sin(t * 2.0);
      positions[idx + 1] = r * Math.sin(t) + 0.025 * Math.sin(t * 3.0);
      positions[idx + 2] = tube * Math.sin(cross + twist) + 0.035 * Math.sin(t * 2.0);
      origins[idx] = Math.random() * 2 - 1;
      origins[idx + 1] = Math.random() * 2 - 1;
      origins[idx + 2] = Math.random() * 2 - 1;
      const ri = i * 4;
      randoms[ri] = Math.random();
      randoms[ri + 1] = Math.random();
      randoms[ri + 2] = Math.random();
      randoms[ri + 3] = Math.random();
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('aOrigin', new THREE.BufferAttribute(origins, 3));
    geometry.setAttribute('aRandom', new THREE.BufferAttribute(randoms, 4));
    geometry.computeBoundingSphere();
    return geometry;
  }

  const vertexShader = `
    uniform float uTime;
    uniform float uDpr;
    uniform float uAspect;
    uniform vec3 uSplats[16];
    attribute vec3 aOrigin;
    attribute vec4 aRandom;
    varying vec3 vColor;
    varying float vAlpha;
    varying float vSparkle;
    void main() {
      float formation = smoothstep(0.0, 3.0, uTime);
      vec3 p = mix(aOrigin, position, formation);
      float t = uTime;
      float phase = aRandom.y * 6.2831853;
      p += vec3(
        sin(t * 0.19 + phase + p.y * 2.2),
        cos(t * 0.16 + phase * 1.7 + p.x * 2.1),
        sin(t * 0.13 + phase + p.x * 1.7)
      ) * (0.003 + aRandom.z * 0.013);
      p.xy += vec2(cos(t * 0.12 + phase), sin(t * 0.14 + phase)) * 0.004;
      vec4 mvPosition = modelViewMatrix * vec4(p, 1.0);
      vec4 clip = projectionMatrix * mvPosition;
      vec2 ndc = clip.xy / max(0.001, clip.w);
      vec2 flow = vec2(0.0);
      for (int i = 0; i < 16; i++) {
        float age = uSplats[i].z;
        if (age >= 0.0 && age < 2.4) {
          vec2 delta = ndc - uSplats[i].xy;
          vec2 aspectDelta = vec2(delta.x * uAspect, delta.y);
          float d2 = dot(aspectDelta, aspectDelta);
          float influence = exp(-d2 * 76.0) * exp(-age * 1.75);
          vec2 swirl = vec2(-delta.y, delta.x);
          flow += swirl * influence * 0.16;
          flow += normalize(delta + vec2(0.00001)) * influence * 0.018;
        }
      }
      clip.xy += flow * clip.w;
      gl_Position = clip;
      float viewDistance = max(0.1, -mvPosition.z);
      gl_PointSize = clamp(uDpr * (1.25 + aRandom.z * 2.3) * (6.0 / viewDistance), 1.0, 8.0);
      float lavender = pow(aRandom.x, 18.0) * 0.92;
      vec3 base = mix(vec3(0.23, 0.235, 0.26), vec3(0.68, 0.51, 1.0), lavender);
      float sparkle = pow(aRandom.w, 34.0) * (0.5 + 0.5 * sin(t * 3.7 + phase * 8.0));
      vColor = base + vec3(sparkle * 0.72);
      vAlpha = 0.56 + aRandom.z * 0.36 + sparkle * 0.35;
      vSparkle = sparkle;
    }
  `;

  const fragmentShader = `
    varying vec3 vColor;
    varying float vAlpha;
    varying float vSparkle;
    void main() {
      vec2 q = gl_PointCoord - vec2(0.5);
      float r = length(q);
      if (r > 0.5) discard;
      float soft = exp(-r * r * 22.0);
      float core = 1.0 - smoothstep(0.02, 0.19, r);
      vec3 color = vColor * (0.62 + soft * 0.58 + core * 0.3 + vSparkle * 0.5);
      float alpha = soft * vAlpha;
      gl_FragColor = vec4(color, alpha);
    }
  `;

  function updateSplatUniforms() {
    if (!splatUniforms) return;
    const values = splatUniforms.value;
    for (let i = 0; i < SPLAT_COUNT; i++) {
      const item = splats[i];
      if (item) values[i].set(item.x, item.y, item.age);
      else values[i].set(0, 0, -1);
    }
  }

  function addSplat(event) {
    if (!canvas || !renderer) return;
    const w = Math.max(1, window.innerWidth), h = Math.max(1, window.innerHeight);
    const x = (event.clientX / w) * 2 - 1;
    const y = 1 - (event.clientY / h) * 2;
    const now = performance.now();
    if (now - lastPointerAt > 50) splats = [];
    lastPointerAt = now;
    splats.unshift({ x, y, age: 0 });
    if (splats.length > SPLAT_COUNT) splats.length = SPLAT_COUNT;
    if (cameraTarget) {
      cameraTarget.x = -1.17 - x * 0.72;
      cameraTarget.y = y * 1.05;
    }
    updateSplatUniforms();
  }

  function resize() {
    if (!renderer || !camera) return;
    const width = Math.max(1, window.innerWidth), height = Math.max(1, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    if (points?.material?.uniforms?.uAspect) points.material.uniforms.uAspect.value = width / height;
  }

  function destroy() {
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
    if (resizeHandler) window.removeEventListener('resize', resizeHandler);
    if (pointerHandler) window.removeEventListener('pointermove', pointerHandler);
    if (pointerDownHandler) window.removeEventListener('pointerdown', pointerDownHandler);
    resizeHandler = pointerHandler = pointerDownHandler = null;
    if (points) {
      points.geometry.dispose();
      points.material.dispose();
      scene?.remove(points);
    }
    if (renderer) renderer.dispose();
    if (canvas) canvas.removeAttribute('style');
    renderer = scene = camera = points = canvas = clock = null;
    splatUniforms = cameraTarget = null;
    splats = [];
  }

  function mount(target) {
    destroy();
    if (!target || !window.THREE || !window.THREE.WebGLRenderer) return;
    canvas = target;
    reducedMotion = Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);
    try {
      renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: false, powerPreference: 'high-performance' });
      renderer.setClearColor(0x000000, 0);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      renderer.setSize(window.innerWidth, window.innerHeight, false);
      scene = new THREE.Scene();
      camera = new THREE.PerspectiveCamera(30, window.innerWidth / Math.max(1, window.innerHeight), 0.1, 1000);
      camera.position.set(-1.17, 0, 6);
      camera.lookAt(0, 0, 0);
      cameraTarget = camera.position.clone();
      clock = new THREE.Clock();
      splats = [];
      splatUniforms = { value: Array.from({ length: SPLAT_COUNT }, () => new THREE.Vector3(0, 0, -1)) };
      const mobile = window.matchMedia?.('(max-width: 760px)').matches || window.innerWidth < 761;
      const count = mobile ? 16384 : 196608;
      const geometry = makeGeometry(count);
      const material = new THREE.ShaderMaterial({
        uniforms: {
          uTime: { value: 0 },
          uDpr: { value: Math.min(window.devicePixelRatio || 1, 2) },
          uAspect: { value: window.innerWidth / Math.max(1, window.innerHeight) },
          uSplats: splatUniforms
        },
        vertexShader,
        fragmentShader,
        transparent: true,
        depthTest: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending
      });
      points = new THREE.Points(geometry, material);
      points.position.set(0.343, 0.16, -1);
      points.rotation.set(-28.4 * Math.PI / 180, 390 * Math.PI / 180, 4.92 * Math.PI / 180);
      points.scale.set(2.4, 2.4, 2.9);
      scene.add(points);
      resizeHandler = resize;
      pointerHandler = addSplat;
      pointerDownHandler = addSplat;
      window.addEventListener('resize', resizeHandler, { passive: true });
      window.addEventListener('pointermove', pointerHandler, { passive: true });
      window.addEventListener('pointerdown', pointerDownHandler, { passive: true });
      const animate = () => {
        frame = requestAnimationFrame(animate);
        if (!renderer || !scene || !camera || document.hidden) return;
        const dt = Math.min(clock.getDelta(), 0.05);
        if (!reducedMotion) {
          points.material.uniforms.uTime.value += dt;
          camera.position.lerp(cameraTarget, 0.05);
          camera.lookAt(0, 0, 0);
          splats.forEach(item => { item.age += dt; });
          splats = splats.filter(item => item.age < 2.4);
          updateSplatUniforms();
        }
        points.material.uniforms.uDpr.value = Math.min(window.devicePixelRatio || 1, 2);
        renderer.render(scene, camera);
      };
      resize();
      animate();
    } catch (error) {
      destroy();
      if (target) target.classList.add('axon-webgl-fallback');
      console.warn('Makia particle field unavailable; using CSS fallback.', error);
    }
  }

  window.MakiaAxon = { mount, destroy };
})();
