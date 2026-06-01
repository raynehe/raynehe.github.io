import * as THREE from "three";
import { OBJLoader } from "three/addons/loaders/OBJLoader.js";

const MANIFEST_URL = "asset/demo/manifest.json";
const ACTIVE_JOINT_TYPES = new Set(["continuous", "revolute", "prismatic"]);
const textFetchCache = new Map();

class DemoViewer {
  constructor(root) {
    this.root = root;
    this.listElement = root.querySelector("[data-demo-list]");
    this.stageElement = root.querySelector("[data-demo-stage]");
    this.jointPanelElement = root.querySelector("[data-joint-panel]");
    this.statusElement = root.querySelector("[data-demo-status]");
    this.titleElement = root.querySelector("[data-demo-title]");
    this.metaElement = root.querySelector("[data-demo-meta]");
    this.resetButton = root.querySelector("[data-demo-reset]");
    this.cases = [];
    this.currentCase = null;
    this.cleanupScene = null;
    this.loadToken = 0;
  }

  async init() {
    this.resetButton?.addEventListener("click", () => {
      if (this.currentCase) {
        this.loadCase(this.currentCase);
      }
    });

    try {
      this.setStatus("Loading demo manifest...");
      const response = await fetch(MANIFEST_URL);
      if (!response.ok) {
        throw new Error(`Could not load ${MANIFEST_URL}.`);
      }

      const manifest = await response.json();
      this.cases = Array.isArray(manifest.cases) ? manifest.cases : [];
      if (!this.cases.length) {
        throw new Error("No demo cases were found in the manifest.");
      }

      this.renderCaseList();
      await this.loadCase(this.cases[0]);
    } catch (error) {
      this.setStatus(error instanceof Error ? error.message : String(error), true);
      this.setPlaceholder("Could not initialize the demo viewer.");
    }
  }

  renderCaseList() {
    if (!this.listElement) {
      return;
    }

    this.listElement.replaceChildren(
      ...this.cases.map((demoCase) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "demo-case-button";
        button.dataset.caseId = demoCase.id;

        const thumb = document.createElement("span");
        thumb.className = "demo-case-thumb";
        renderCaseThumbnail(thumb, demoCase);

        const label = document.createElement("span");
        label.className = "demo-case-title";
        label.textContent = demoCase.title;

        button.append(thumb, label);
        button.addEventListener("click", () => this.loadCase(demoCase));
        return button;
      }),
    );
  }

  async loadCase(demoCase) {
    const loadToken = this.loadToken + 1;
    this.loadToken = loadToken;
    this.currentCase = demoCase;
    this.setActiveCase(demoCase.id);
    this.disposeScene();
    this.setTitle(demoCase.title, demoCase.source === "urdf-obj" ? "Loading URDF and OBJ mesh assets." : "Loading flattened USD and URDF articulation.");
    this.setStatus("Loading scene assets...");
    this.setPlaceholder("Loading 3D scene...");
    this.renderJointPanel([]);

    try {
      const parsedScene = demoCase.source === "urdf-obj"
        ? await loadUrdfObjScene(demoCase)
        : await loadUsdUrdfScene(demoCase);

      if (this.loadToken !== loadToken) {
        return;
      }

      await yieldToBrowser();
      if (this.loadToken !== loadToken) {
        return;
      }

      this.buildScene(parsedScene, demoCase);
    } catch (error) {
      if (this.loadToken !== loadToken) {
        return;
      }
      this.disposeScene();
      this.setStatus(error instanceof Error ? error.message : String(error), true);
      this.setPlaceholder("This case could not be loaded.");
      this.setTitle(demoCase.title, "Preview unavailable.");
    }
  }

  buildScene(parsedScene, demoCase) {
    const sceneRuntime = createThreeRuntime({
      stageElement: this.stageElement,
      jointPanelElement: this.jointPanelElement,
      parsedScene,
      setStatus: (message, isError) => this.setStatus(message, isError),
    });

    this.cleanupScene = sceneRuntime.cleanup;
    this.setTitle(demoCase.title, "");
    this.setStatus("Scene ready. Drag to rotate and scroll to zoom.");
  }

  disposeScene() {
    if (this.cleanupScene) {
      this.cleanupScene();
      this.cleanupScene = null;
    }
  }

  setActiveCase(caseId) {
    this.listElement?.querySelectorAll(".demo-case-button").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.caseId === caseId);
    });
  }

  setTitle(title, meta) {
    if (this.titleElement) {
      this.titleElement.textContent = title;
    }
    if (this.metaElement) {
      this.metaElement.textContent = meta;
      this.metaElement.hidden = !meta;
    }
  }

  setStatus(message, isError = false) {
    if (!this.statusElement) {
      return;
    }
    this.statusElement.textContent = message;
    this.statusElement.classList.toggle("is-error", isError);
  }

  setPlaceholder(message) {
    if (!this.stageElement) {
      return;
    }
    this.stageElement.replaceChildren();
    const placeholder = document.createElement("div");
    placeholder.className = "demo-stage-placeholder";
    const label = document.createElement("span");
    label.textContent = message;
    placeholder.append(label);
    this.stageElement.append(placeholder);
  }

  renderJointPanel(joints) {
    renderJointPanel(this.jointPanelElement, joints);
  }
}

function renderCaseThumbnail(container, demoCase) {
  if (!demoCase.thumbnail) {
    renderCaseThumbnailFallback(container, demoCase.title);
    return;
  }

  const image = document.createElement("img");
  image.src = demoCase.thumbnail;
  image.alt = demoCase.title;
  image.loading = "lazy";
  image.decoding = "async";
  image.addEventListener("error", () => renderCaseThumbnailFallback(container, demoCase.title), { once: true });
  container.replaceChildren(image);
}

function renderCaseThumbnailFallback(container, title) {
  const fallback = document.createElement("span");
  fallback.className = "demo-case-thumb-fallback";
  fallback.textContent = initialsForTitle(title);
  container.replaceChildren(fallback);
}

function initialsForTitle(title) {
  return title
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? "")
    .join("");
}

async function loadUsdUrdfScene(demoCase) {
  const [usdText, urdfText] = await Promise.all([
    fetchText(demoCase.previewUsd),
    fetchText(demoCase.urdf),
  ]);

  if (!usdText.trimStart().startsWith("#usda")) {
    throw new Error("The preview USD must be flattened text USDA.");
  }

  return {
    usd: parseUsdText(usdText),
    urdf: parseUrdfText(urdfText),
  };
}

async function loadUrdfObjScene(demoCase) {
  const urdfText = await fetchText(demoCase.urdf);
  const urdf = parseUrdfText(urdfText);
  const meshBaseUrl = new URL(demoCase.meshBasePath ?? "./", window.location.href);
  const visualJobs = [];

  for (const link of urdf.links.values()) {
    for (const visual of link.visuals) {
      if (!visual.filename) {
        continue;
      }

      visualJobs.push({
        visual,
        linkName: link.name,
        meshBaseUrl,
        visualIndex: visualJobs.length,
      });
    }
  }

  const objectVisuals = await Promise.all(visualJobs.map(async (job) => {
    const object = await loadObjVisual(job);
    return {
      linkName: job.linkName,
      name: job.visual.name || job.visual.filename,
      origin: job.visual.origin,
      scale: job.visual.scale,
      object,
    };
  }));

  if (!objectVisuals.length) {
    throw new Error("No visual OBJ meshes were found in the URDF.");
  }

  return {
    usd: { meshes: [] },
    urdf,
    objectVisuals,
    meshCount: objectVisuals.length,
  };
}

function createThreeRuntime({ stageElement, jointPanelElement, parsedScene, setStatus }) {
  if (!stageElement) {
    throw new Error("Missing demo stage element.");
  }

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x000000, 0);
  renderer.domElement.style.display = "block";
  renderer.domElement.style.width = "100%";
  renderer.domElement.style.height = "100%";
  stageElement.replaceChildren(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 1000);
  const modelRoot = new THREE.Group();
  modelRoot.rotation.x = -Math.PI / 2;
  scene.add(modelRoot);

  scene.add(new THREE.HemisphereLight(0xffffff, 0x1c2435, 2.2));
  const keyLight = new THREE.DirectionalLight(0xffffff, 2.8);
  keyLight.position.set(4, 7, 6);
  scene.add(keyLight);

  const fillLight = new THREE.DirectionalLight(0x8fdfff, 0.8);
  fillLight.position.set(-5, 3, -4);
  scene.add(fillLight);

  const linkGroups = new Map();
  const jointRuntimes = new Map();
  const materials = [];

  const ensureLinkGroup = (linkName) => {
    if (!linkGroups.has(linkName)) {
      const group = new THREE.Group();
      group.name = linkName;
      group.userData.linkName = linkName;
      linkGroups.set(linkName, group);
    }
    return linkGroups.get(linkName);
  };

  for (const linkName of parsedScene.urdf.links.keys()) {
    ensureLinkGroup(linkName);
  }

  for (const visual of parsedScene.objectVisuals ?? []) {
    const visualGroup = new THREE.Group();
    visualGroup.name = visual.name;
    visualGroup.position.set(visual.origin.xyz[0], visual.origin.xyz[1], visual.origin.xyz[2]);
    visualGroup.rotation.set(visual.origin.rpy[0], visual.origin.rpy[1], visual.origin.rpy[2], "XYZ");
    visualGroup.scale.set(visual.scale[0], visual.scale[1], visual.scale[2]);
    visualGroup.add(visual.object);
    ensureLinkGroup(visual.linkName).add(visualGroup);
  }

  parsedScene.usd.meshes.forEach((meshData, index) => {
    const linkName = meshData.linkName || meshData.name || `mesh-${index + 1}`;
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(meshData.positions, 3));
    geometry.setIndex(meshData.indices);
    geometry.computeVertexNormals();

    const color = parsedScene.urdf.links.get(linkName)?.color ?? fallbackColor(index);
    const material = new THREE.MeshStandardMaterial({
      color: new THREE.Color(color[0], color[1], color[2]),
      roughness: 0.62,
      metalness: 0.08,
      side: THREE.DoubleSide,
    });
    materials.push(material);

    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = meshData.name;
    ensureLinkGroup(linkName).add(mesh);
  });

  const childLinks = new Set();
  for (const joint of parsedScene.urdf.joints) {
    childLinks.add(joint.child);
  }

  for (const joint of parsedScene.urdf.joints) {
    const parentGroup = ensureLinkGroup(joint.parent);
    const childGroup = ensureLinkGroup(joint.child);
    const originGroup = new THREE.Group();
    const motionGroup = new THREE.Group();

    originGroup.name = `${joint.name}_origin`;
    motionGroup.name = `${joint.name}_motion`;
    originGroup.position.set(joint.origin.xyz[0], joint.origin.xyz[1], joint.origin.xyz[2]);
    originGroup.rotation.set(joint.origin.rpy[0], joint.origin.rpy[1], joint.origin.rpy[2], "XYZ");

    parentGroup.add(originGroup);
    originGroup.add(motionGroup);
    motionGroup.add(childGroup);

    if (ACTIVE_JOINT_TYPES.has(joint.type)) {
      const runtime = {
        joint,
        originGroup,
        motionGroup,
        axis: new THREE.Vector3(joint.axis[0], joint.axis[1], joint.axis[2]).normalize(),
        value: defaultJointValue(joint),
      };
      jointRuntimes.set(joint.name, runtime);
      applyJointRuntime(runtime, runtime.value);
    }
  }

  let rootLinkCount = 0;
  for (const [linkName, group] of linkGroups) {
    if (!childLinks.has(linkName)) {
      modelRoot.add(group);
      rootLinkCount += 1;
    }
  }

  if (rootLinkCount === 0) {
    for (const group of linkGroups.values()) {
      modelRoot.add(group);
    }
  }

  const box = new THREE.Box3().setFromObject(modelRoot);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  modelRoot.position.sub(center);
  const maxSize = Math.max(size.x, size.y, size.z) || 1;

  const grid = new THREE.GridHelper(maxSize * 2.2, 14, 0x59f1ff, 0x263241);
  grid.position.y = -size.y / 2 - 0.02;
  scene.add(grid);

  let cameraDistance = maxSize * 2.6;
  let orbitPitch = 0.35;
  let orbitYaw = 0.78;
  let dragMode = "none";
  let previousX = 0;
  let previousY = 0;

  function resize() {
    const width = stageElement.clientWidth || 640;
    const height = stageElement.clientHeight || 420;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }

  function render() {
    renderer.render(scene, camera);
  }

  function updateCamera() {
    orbitPitch = Math.max(-1.1, Math.min(1.2, orbitPitch));
    const horizontalDistance = Math.cos(orbitPitch) * cameraDistance;
    camera.position.set(
      Math.sin(orbitYaw) * horizontalDistance,
      Math.sin(orbitPitch) * cameraDistance,
      Math.cos(orbitYaw) * horizontalDistance,
    );
    camera.lookAt(0, 0, 0);
    render();
  }

  function handlePointerDown(event) {
    previousX = event.clientX;
    previousY = event.clientY;
    renderer.domElement.setPointerCapture?.(event.pointerId);
    dragMode = "orbit";
    render();
  }

  function handlePointerMove(event) {
    if (dragMode !== "orbit") {
      return;
    }

    const deltaX = event.clientX - previousX;
    const deltaY = event.clientY - previousY;
    previousX = event.clientX;
    previousY = event.clientY;

    orbitYaw += deltaX * 0.008;
    orbitPitch += deltaY * 0.008;
    updateCamera();
  }

  function handlePointerUp(event) {
    dragMode = "none";
    if (renderer.domElement.hasPointerCapture?.(event.pointerId)) {
      renderer.domElement.releasePointerCapture(event.pointerId);
    }
  }

  function handleWheel(event) {
    event.preventDefault();
    cameraDistance *= event.deltaY > 0 ? 1.08 : 0.92;
    cameraDistance = Math.max(maxSize * 0.45, Math.min(maxSize * 8, cameraDistance));
    updateCamera();
  }

  function handleJointChange(jointName, value) {
    const runtime = jointRuntimes.get(jointName);
    if (!runtime) {
      return;
    }
    runtime.value = value;
    applyJointRuntime(runtime, value);
    render();
  }

  const resizeObserver = new ResizeObserver(() => {
    resize();
    render();
  });
  resizeObserver.observe(stageElement);

  renderer.domElement.addEventListener("pointerdown", handlePointerDown);
  renderer.domElement.addEventListener("pointermove", handlePointerMove);
  renderer.domElement.addEventListener("pointerup", handlePointerUp);
  renderer.domElement.addEventListener("pointercancel", handlePointerUp);
  renderer.domElement.addEventListener("wheel", handleWheel, { passive: false });

  renderJointPanel(
    jointPanelElement,
    Array.from(jointRuntimes.values()).map((runtime) => ({
      joint: runtime.joint,
      value: runtime.value,
      onChange: handleJointChange,
    })),
  );

  resize();
  updateCamera();
  setStatus("Scene ready.");

  return {
    cleanup() {
      resizeObserver.disconnect();
      renderer.domElement.removeEventListener("pointerdown", handlePointerDown);
      renderer.domElement.removeEventListener("pointermove", handlePointerMove);
      renderer.domElement.removeEventListener("pointerup", handlePointerUp);
      renderer.domElement.removeEventListener("pointercancel", handlePointerUp);
      renderer.domElement.removeEventListener("wheel", handleWheel);

      scene.traverse((object) => {
        if (object.geometry) {
          object.geometry.dispose();
        }
        if (object.material instanceof THREE.Material) {
          object.material.dispose();
        } else if (Array.isArray(object.material)) {
          object.material.forEach((material) => material.dispose());
        }
      });
      materials.forEach((material) => material.dispose());
      renderer.dispose();
      stageElement.replaceChildren();
    },
  };
}

function renderJointPanel(panelElement, jointControls) {
  if (!panelElement) {
    return;
  }

  panelElement.replaceChildren();
  const title = document.createElement("p");
  title.className = "demo-panel-title";
  title.textContent = "Joints";
  panelElement.append(title);

  if (!jointControls.length) {
    const empty = document.createElement("p");
    empty.className = "demo-panel-empty";
    empty.textContent = "This case has no controllable joints.";
    panelElement.append(empty);
    return;
  }

  for (const control of jointControls) {
    const { joint, onChange } = control;
    const limits = sliderLimits(joint);
    const jointLabel = compactName(joint.name);
    const wrapper = document.createElement("div");
    wrapper.className = "demo-joint-control";

    const label = document.createElement("label");
    const name = document.createElement("span");
    name.className = "demo-joint-name";
    name.textContent = jointLabel;

    const input = document.createElement("input");
    input.type = "range";
    input.min = String(limits.min);
    input.max = String(limits.max);
    input.step = String(limits.step);
    input.value = String(control.value);
    input.setAttribute("aria-label", jointLabel);

    input.addEventListener("input", () => {
      const value = Number(input.value);
      onChange(joint.name, value);
    });

    label.append(name);
    wrapper.append(label, input);
    panelElement.append(wrapper);
  }
}

function applyJointRuntime(runtime, value) {
  const { joint, motionGroup, axis } = runtime;
  motionGroup.position.set(0, 0, 0);
  motionGroup.quaternion.identity();

  if (joint.type === "prismatic") {
    motionGroup.position.copy(axis).multiplyScalar(value);
  } else if (joint.type === "continuous" || joint.type === "revolute") {
    motionGroup.quaternion.setFromAxisAngle(axis, THREE.MathUtils.degToRad(value));
  }
}

function defaultJointValue(joint) {
  const limits = sliderLimits(joint);
  return limits.min;
}

function sliderLimits(joint) {
  if (joint.type === "prismatic") {
    const min = Number.isFinite(joint.limit.lower) ? joint.limit.lower : -0.5;
    const max = Number.isFinite(joint.limit.upper) ? joint.limit.upper : 0.5;
    return { min, max, step: Math.max((max - min) / 100, 0.001) };
  }

  if (joint.type === "revolute" && Number.isFinite(joint.limit.lower) && Number.isFinite(joint.limit.upper)) {
    return {
      min: Math.round(THREE.MathUtils.radToDeg(joint.limit.lower)),
      max: Math.round(THREE.MathUtils.radToDeg(joint.limit.upper)),
      step: 1,
    };
  }

  return { min: -180, max: 180, step: 1 };
}

function compactName(value) {
  return value.replace(/_joint$/i, "").replace(/_/g, " ");
}

async function loadObjVisual({ visual, meshBaseUrl, visualIndex }) {
  const objUrl = new URL(visual.filename, meshBaseUrl).href;
  const objText = await fetchText(objUrl);
  const materialColors = await loadObjMaterialColors(objText, objUrl);
  const object = new OBJLoader().parse(objText);
  const baseColor = visual.color ?? fallbackColor(visualIndex);
  let meshCount = 0;

  object.traverse((child) => {
    if (!child.isMesh) {
      return;
    }

    meshCount += 1;
    if (!child.geometry.getAttribute("normal")) {
      child.geometry.computeVertexNormals();
    }
    child.material = replaceObjMaterial(child.material, materialColors, baseColor);
  });

  if (!meshCount) {
    throw new Error(`No supported mesh geometry was found in ${visual.filename}.`);
  }

  return object;
}

async function loadObjMaterialColors(objText, objUrl) {
  const materialFiles = [...new Set(
    Array.from(objText.matchAll(/^mtllib\s+(.+)$/gm))
      .flatMap((match) => match[1].trim().split(/\s+/))
      .filter(Boolean),
  )];
  const colors = new Map();

  await Promise.all(materialFiles.map(async (fileName) => {
    const mtlUrl = new URL(fileName, new URL("./", objUrl)).href;
    const mtlText = await fetchText(mtlUrl);
    for (const [name, color] of parseMtlColors(mtlText)) {
      colors.set(name, color);
    }
  }));

  return colors;
}

function parseMtlColors(text) {
  const colors = new Map();
  let materialName = null;

  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }

    const newMaterial = /^newmtl\s+(.+)$/.exec(trimmed);
    if (newMaterial) {
      materialName = newMaterial[1].trim();
      continue;
    }

    const diffuse = /^Kd\s+(.+)$/.exec(trimmed);
    if (materialName && diffuse) {
      const values = diffuse[1].trim().split(/\s+/).map(Number).slice(0, 3);
      if (values.length === 3 && values.every(Number.isFinite)) {
        colors.set(materialName, values);
      }
    }
  }

  return colors;
}

function replaceObjMaterial(material, materialColors, fallback) {
  if (Array.isArray(material)) {
    const replacement = material.map((entry, index) => createObjMaterial(entry?.name ?? `material-${index}`, materialColors, fallback));
    material.forEach(disposeMaterial);
    return replacement;
  }

  const replacement = createObjMaterial(material?.name ?? "material", materialColors, fallback);
  disposeMaterial(material);
  return replacement;
}

function createObjMaterial(name, materialColors, fallback) {
  const color = materialColors.get(name) ?? fallback;
  const material = new THREE.MeshStandardMaterial({
    color: new THREE.Color(color[0], color[1], color[2]),
    roughness: 0.62,
    metalness: 0.08,
    side: THREE.DoubleSide,
  });
  material.name = name;
  return material;
}

function disposeMaterial(material) {
  if (material instanceof THREE.Material) {
    material.dispose();
  }
}

function parseUsdText(text) {
  const xformBlocks = extractXformBlocks(text);
  const meshBlocks = extractMeshBlocks(text, xformBlocks);
  const meshes = meshBlocks.map(parseMeshBlock).filter(Boolean);

  if (!meshes.length) {
    throw new Error("No supported Mesh prims were found in the flattened USDA.");
  }

  return { meshes };
}

function extractMeshBlocks(text, xformBlocks) {
  const blocks = [];
  const meshRegex = /def\s+Mesh\s+"([^"]+)"/g;
  let match = null;

  while ((match = meshRegex.exec(text))) {
    let start = match.index + match[0].length;
    while (/\s/.test(text[start] ?? "")) {
      start += 1;
    }

    if (text[start] === "(") {
      start = skipBalancedBlock(text, start, "(", ")");
      while (/\s/.test(text[start] ?? "")) {
        start += 1;
      }
    }

    if (text[start] !== "{") {
      continue;
    }

    start += 1;
    let depth = 1;
    let cursor = start;
    while (cursor < text.length && depth > 0) {
      const char = text[cursor];
      if (char === "{") {
        depth += 1;
      } else if (char === "}") {
        depth -= 1;
      }
      cursor += 1;
    }

    const ownerPath = readOwnerPath(match.index, xformBlocks);
    blocks.push({
      name: match[1],
      body: text.slice(start, cursor - 1),
      ownerPath,
      linkName: ownerPath.split("/").filter(Boolean).at(-1) ?? match[1],
    });
  }

  return blocks;
}

function extractXformBlocks(text) {
  const blocks = [];
  const stack = [];
  const tokenRegex = /def\s+Xform\s+"([^"]+)"|[{}]/g;
  let depth = 0;
  let pendingXform = null;
  let match = null;

  while ((match = tokenRegex.exec(text))) {
    if (match[1]) {
      pendingXform = {
        name: match[1],
        start: match.index,
      };
      continue;
    }

    if (match[0] === "{") {
      depth += 1;
      if (pendingXform) {
        const parentPath = stack.length ? stack[stack.length - 1].path : "";
        stack.push({
          name: pendingXform.name,
          path: `${parentPath}/${pendingXform.name}`,
          depth,
          start: pendingXform.start,
        });
        pendingXform = null;
      }
    } else {
      while (stack.length && stack[stack.length - 1].depth === depth) {
        const block = stack.pop();
        blocks.push({
          path: block.path,
          start: block.start,
          end: match.index,
        });
      }
      depth = Math.max(0, depth - 1);
      pendingXform = null;
    }
  }

  return blocks;
}

function readOwnerPath(meshIndex, xformBlocks) {
  let ownerPath = "";
  let ownerSpan = Number.POSITIVE_INFINITY;

  for (const block of xformBlocks) {
    if (block.start < meshIndex && meshIndex < block.end) {
      const span = block.end - block.start;
      if (span < ownerSpan) {
        ownerPath = block.path;
        ownerSpan = span;
      }
    }
  }

  return ownerPath;
}

function parseMeshBlock(block, index) {
  const pointValues = readUsdArray(block.body, /point3f\[\]\s+points\s*=\s*\[/);
  const countValues = readUsdArray(block.body, /int\[\]\s+faceVertexCounts\s*=\s*\[/);
  const indexValues = readUsdArray(block.body, /int\[\]\s+faceVertexIndices\s*=\s*\[/);

  if (!pointValues || !countValues || !indexValues) {
    return null;
  }

  const positions = parseNumbers(pointValues);
  const counts = parseNumbers(countValues).map((value) => Math.trunc(value));
  const polygonIndices = parseNumbers(indexValues).map((value) => Math.trunc(value));
  const indices = [];
  let offset = 0;

  for (const count of counts) {
    const face = polygonIndices.slice(offset, offset + count);
    offset += count;
    for (let i = 1; i < face.length - 1; i += 1) {
      indices.push(face[0], face[i], face[i + 1]);
    }
  }

  if (positions.length < 9 || indices.length < 3) {
    return null;
  }

  return {
    name: block.name || `mesh-${index + 1}`,
    linkName: block.linkName,
    positions,
    indices,
  };
}

function readUsdArray(text, startPattern) {
  const match = startPattern.exec(text);
  if (!match) {
    return null;
  }

  let cursor = match.index + match[0].length;
  let depth = 1;
  while (cursor < text.length && depth > 0) {
    const char = text[cursor];
    if (char === "[") {
      depth += 1;
    } else if (char === "]") {
      depth -= 1;
    }
    cursor += 1;
  }

  return text.slice(match.index + match[0].length, cursor - 1);
}

function skipBalancedBlock(text, start, open, close) {
  let depth = 0;
  let cursor = start;

  while (cursor < text.length) {
    const char = text[cursor];
    if (char === open) {
      depth += 1;
    } else if (char === close) {
      depth -= 1;
      if (depth === 0) {
        return cursor + 1;
      }
    }
    cursor += 1;
  }

  return start;
}

function parseUrdfText(text) {
  const document = new DOMParser().parseFromString(text, "application/xml");
  const parserError = document.querySelector("parsererror");
  if (parserError) {
    throw new Error("Could not parse the URDF file.");
  }

  const links = new Map();
  for (const linkElement of Array.from(document.getElementsByTagName("link"))) {
    const name = linkElement.getAttribute("name");
    if (!name) {
      continue;
    }

    const visuals = Array.from(linkElement.children)
      .filter((child) => child.tagName === "visual")
      .map(parseUrdfVisual)
      .filter(Boolean);

    const firstColor = visuals.find((visual) => visual.color)?.color ?? null;
    links.set(name, {
      name,
      color: firstColor,
      visuals,
    });
  }

  const joints = [];
  for (const jointElement of Array.from(document.getElementsByTagName("joint"))) {
    const name = jointElement.getAttribute("name") ?? "joint";
    const type = jointElement.getAttribute("type") ?? "fixed";
    const parent = jointElement.getElementsByTagName("parent")[0]?.getAttribute("link");
    const child = jointElement.getElementsByTagName("child")[0]?.getAttribute("link");

    if (!parent || !child) {
      continue;
    }

    const originElement = jointElement.getElementsByTagName("origin")[0];
    const axisElement = jointElement.getElementsByTagName("axis")[0];
    const limitElement = jointElement.getElementsByTagName("limit")[0];

    joints.push({
      name,
      type,
      parent,
      child,
      origin: {
        xyz: parseVector(originElement?.getAttribute("xyz"), [0, 0, 0]),
        rpy: parseVector(originElement?.getAttribute("rpy"), [0, 0, 0]),
      },
      axis: parseVector(axisElement?.getAttribute("xyz"), [1, 0, 0]),
      limit: {
        lower: parseOptionalNumber(limitElement?.getAttribute("lower")),
        upper: parseOptionalNumber(limitElement?.getAttribute("upper")),
      },
    });
  }

  return { links, joints };
}

function parseUrdfVisual(visualElement) {
  const meshElement = visualElement.getElementsByTagName("mesh")[0];
  const filename = meshElement?.getAttribute("filename");
  if (!filename) {
    return null;
  }

  const originElement = visualElement.getElementsByTagName("origin")[0];
  const colorElement = visualElement.getElementsByTagName("color")[0];
  return {
    name: visualElement.getAttribute("name") ?? filename,
    filename,
    origin: {
      xyz: parseVector(originElement?.getAttribute("xyz"), [0, 0, 0]),
      rpy: parseVector(originElement?.getAttribute("rpy"), [0, 0, 0]),
    },
    scale: parseVector(meshElement.getAttribute("scale"), [1, 1, 1]),
    color: parseColor(colorElement?.getAttribute("rgba")),
  };
}

function parseVector(value, fallback) {
  if (!value) {
    return fallback;
  }
  const parsed = value.trim().split(/\s+/).map(Number);
  return parsed.length >= fallback.length && parsed.every(Number.isFinite) ? parsed.slice(0, fallback.length) : fallback;
}

function parseColor(value) {
  if (!value) {
    return null;
  }
  const color = parseVector(value, [0.35, 0.82, 0.9, 1]);
  return color.slice(0, 3);
}

function parseOptionalNumber(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function parseNumbers(value) {
  return (value.match(/-?\d+(?:\.\d+)?(?:e[-+]?\d+)?/gi) ?? []).map(Number);
}

function fallbackColor(index) {
  const colors = [
    [0.35, 0.84, 0.94],
    [0.49, 0.88, 0.71],
    [0.9, 0.75, 0.42],
    [0.9, 0.5, 0.5],
  ];
  return colors[index % colors.length];
}

async function fetchText(url) {
  const requestUrl = new URL(url, window.location.href).href;
  if (textFetchCache.has(requestUrl)) {
    return textFetchCache.get(requestUrl);
  }

  const fetchPromise = fetch(requestUrl).then((response) => {
    if (!response.ok) {
      throw new Error(`Could not load ${url}.`);
    }
    return response.text();
  });

  textFetchCache.set(requestUrl, fetchPromise);

  try {
    return await fetchPromise;
  } catch (error) {
    textFetchCache.delete(requestUrl);
    throw error;
  }
}

function yieldToBrowser() {
  return new Promise((resolve) => window.setTimeout(resolve, 0));
}

document.querySelectorAll("[data-demo-viewer]").forEach((element) => {
  new DemoViewer(element).init();
});
