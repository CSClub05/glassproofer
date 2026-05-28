const form = document.querySelector('#upload-form');
const input = document.querySelector('#schematic-file');
const fileLabel = document.querySelector('#file-label');
const statusBox = document.querySelector('#status');
const button = document.querySelector('#submit-button');
const mappingBlockInput = document.querySelector('#mapping-block');
const mappingColorSelect = document.querySelector('#mapping-color');
const addMappingButton = document.querySelector('#add-mapping');
const clearMappingsButton = document.querySelector('#clear-mappings');
const mappingTableBody = document.querySelector('#mapping-table-body');

const API_BASE = 'https://glass-spawnproofer-api.onrender.com';

const API_URL = `${API_BASE}/api/mark-spawns`;
const MAPPINGS_URL = `${API_BASE}/api/glass-mappings`;

const STORAGE_KEY = 'minecraft-spawn-marker.custom-glass-mappings.v1';

const FALLBACK_COLORS = [
  'white', 'orange', 'magenta', 'light_blue', 'yellow', 'lime', 'pink', 'gray',
  'light_gray', 'cyan', 'purple', 'blue', 'brown', 'green', 'red', 'black',
].map((color) => ({
  color,
  label: color.replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
  block_id: `minecraft:${color}_stained_glass`,
}));

let colorOptions = FALLBACK_COLORS;
let customMappings = loadCustomMappings();

input.addEventListener('change', () => {
  fileLabel.textContent = input.files?.[0]?.name || 'Choose a .litematic file';
});

function setStatus(message, type = '') {
  statusBox.textContent = message;
  statusBox.className = `status ${type}`.trim();
}

function normalizeBlockId(blockId) {
  let clean = String(blockId || '').trim().toLowerCase();
  if (clean.includes('[')) clean = clean.split('[', 1)[0];
  if (!clean) return '';
  if (!clean.includes(':')) clean = `minecraft:${clean}`;
  return clean;
}

function loadCustomMappings() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
  } catch (_) {
    return {};
  }
}

function saveCustomMappings() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(customMappings, null, 2));
}

function renderColorOptions() {
  mappingColorSelect.innerHTML = '';
  for (const option of colorOptions) {
    const element = document.createElement('option');
    element.value = option.block_id;
    element.textContent = option.label;
    mappingColorSelect.appendChild(element);
  }
}

function renderMappingTable() {
  const entries = Object.entries(customMappings).sort(([a], [b]) => a.localeCompare(b));
  mappingTableBody.innerHTML = '';

  if (entries.length === 0) {
    const row = document.createElement('tr');
    row.className = 'empty-row';
    row.innerHTML = '<td colspan="3">No custom mappings yet.</td>';
    mappingTableBody.appendChild(row);
    return;
  }

  for (const [blockId, glassId] of entries) {
    const row = document.createElement('tr');

    const blockCell = document.createElement('td');
    blockCell.textContent = blockId;

    const glassCell = document.createElement('td');
    glassCell.textContent = glassId;

    const actionCell = document.createElement('td');
    const removeButton = document.createElement('button');
    removeButton.type = 'button';
    removeButton.className = 'table-button';
    removeButton.textContent = 'Remove';
    removeButton.addEventListener('click', () => {
      delete customMappings[blockId];
      saveCustomMappings();
      renderMappingTable();
    });
    actionCell.appendChild(removeButton);

    row.append(blockCell, glassCell, actionCell);
    mappingTableBody.appendChild(row);
  }
}

addMappingButton.addEventListener('click', () => {
  const blockId = normalizeBlockId(mappingBlockInput.value);
  const glassId = mappingColorSelect.value;

  if (!blockId) {
    setStatus('Enter a floor block ID before adding a mapping.', 'error');
    mappingBlockInput.focus();
    return;
  }

  customMappings[blockId] = glassId;
  saveCustomMappings();
  renderMappingTable();
  mappingBlockInput.value = '';
  mappingBlockInput.focus();
  setStatus(`Saved custom mapping for ${blockId}.`, 'success');
});

clearMappingsButton.addEventListener('click', () => {
  customMappings = {};
  saveCustomMappings();
  renderMappingTable();
  setStatus('Custom mappings cleared.', 'success');
});

async function loadServerMappings() {
  try {
    const response = await fetch(MAPPINGS_URL);
    if (!response.ok) return;
    const data = await response.json();
    if (Array.isArray(data.colors) && data.colors.length > 0) {
      colorOptions = data.colors;
      renderColorOptions();
    }
  } catch (_) {
    // The frontend still works with fallback color options if the backend is not running yet.
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();

  const file = input.files?.[0];
  if (!file) {
    setStatus('Choose a schematic file first.', 'error');
    return;
  }

  const formData = new FormData();
  formData.append('file', file);
  formData.append('glass_mappings_json', JSON.stringify(customMappings));

  button.disabled = true;
  setStatus('Processing schematic...');

  try {
    const response = await fetch(API_URL, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      let message = `Request failed with status ${response.status}`;
      try {
        const body = await response.json();
        message = body.detail || message;
      } catch (_) {}
      throw new Error(message);
    }

    const blob = await response.blob();
    const placed = response.headers.get('X-Glass-Placed') || '?';
    const candidates = response.headers.get('X-Spawn-Candidates') || '?';

    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = file.name.replace(/\.[^.]+$/, '') + '_glass_spawnproofed.litematic';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);

    setStatus(`Done. Found ${candidates} potential spaces and placed ${placed} glass markers.`, 'success');
  } catch (error) {
    setStatus(error.message, 'error');
  } finally {
    button.disabled = false;
  }
});

renderColorOptions();
renderMappingTable();
loadServerMappings();
