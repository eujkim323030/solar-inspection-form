// 태양광 수검자 서식 공용 저장소 (관리자 구글 계정의 Apps Script에 붙여넣기)
// 패드·폰이 팀 코드로 현장(서식에 적은 내용·손글씨·서명)을 주고받는다.
// 파일은 '내 드라이브 > 수검자서식 백업' 폴더에 쌓이고, 지운 현장은 그 안의 '삭제됨' 폴더로 옮겨 보관한다.
const TEAM_CODE = '여기에-팀-코드';   // ← 붙여넣은 뒤 원하는 코드로 바꾸세요 (예: 482915). 패드·폰에서 처음 한 번 입력합니다.
const FOLDER_NAME = '수검자서식 백업';
const INDEX = 'suggeom_index.json';   // 현장 목록 (id → 버전·현장 이름·삭제 여부)
const MAX_BYTES = 40 * 1024 * 1024;

function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    const body = e.postData.contents;
    if (body.length > MAX_BYTES) return reply({ ok: false, error: 'too large' });
    const req = JSON.parse(body);
    if (req.app !== 'suggeom') return reply({ ok: false, error: 'bad data' });
    if (String(req.code) !== TEAM_CODE) return reply({ ok: false, error: 'bad code' });
    lock.waitLock(25000); // 여러 기기가 동시에 써도 목록이 꼬이지 않게 한 번에 하나씩
    const folder = getFolder();
    switch (req.action) {
      case 'ping': return reply({ ok: true });
      case 'list': return reply({ ok: true, index: loadIndex(folder) });
      case 'get': return reply({ ok: true, sites: req.ids.slice(0, 3).map(id => readSite(folder, id)).filter(Boolean) });
      case 'put': return reply(putSite(folder, req.site));
      case 'delete': return reply(deleteSite(folder, req.id));
    }
    return reply({ ok: false, error: 'bad action' });
  } catch (err) {
    return reply({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}

const okId = id => /^[a-z0-9]{6,30}$/.test(id);

function putSite(folder, s) {
  if (!s || !okId(s.id)) return { ok: false, error: 'bad id' };
  trashFiles(folder, s.id); // 같은 현장이 다시 오면 옛 파일은 휴지통으로
  const name = ('수검자서식_' + s.name + '_' + s.id + '.txt').replace(/[\\/:*?"<>|]/g, '_');
  folder.createFile(name, JSON.stringify({ app: 'suggeom', version: 1, sites: [s] }), MimeType.PLAIN_TEXT);
  const index = loadIndex(folder);
  index[s.id] = { ver: s.updatedAt, name: s.name };
  writeJson(folder, INDEX, index);
  return { ok: true };
}

function deleteSite(folder, id) {
  if (!okId(id)) return { ok: false, error: 'bad id' };
  const bin = subFolder(folder, '삭제됨');
  const it = folder.searchFiles("title contains '" + id + "' and trashed = false");
  while (it.hasNext()) it.next().moveTo(bin);
  const index = loadIndex(folder);
  index[id] = Object.assign(index[id] || {}, { deleted: true, deletedAt: new Date().toISOString() });
  writeJson(folder, INDEX, index);
  return { ok: true };
}

function readSite(folder, id) {
  if (!okId(id)) return null;
  const it = folder.searchFiles("title contains '" + id + "' and trashed = false");
  return it.hasNext() ? JSON.parse(it.next().getBlob().getDataAsString()).sites[0] : null;
}

function loadIndex(folder) {
  return readJson(folder, INDEX) || {};
}

function trashFiles(folder, id) {
  const it = folder.searchFiles("title contains '" + id + "' and trashed = false");
  while (it.hasNext()) it.next().setTrashed(true);
}

function readJson(folder, name) {
  const it = folder.getFilesByName(name);
  return it.hasNext() ? JSON.parse(it.next().getBlob().getDataAsString()) : null;
}

function writeJson(folder, name, obj) {
  const it = folder.getFilesByName(name);
  if (it.hasNext()) it.next().setContent(JSON.stringify(obj));
  else folder.createFile(name, JSON.stringify(obj), MimeType.PLAIN_TEXT);
}

function getFolder() {
  const it = DriveApp.getFoldersByName(FOLDER_NAME);
  return it.hasNext() ? it.next() : DriveApp.createFolder(FOLDER_NAME);
}

function subFolder(folder, name) {
  const it = folder.getFoldersByName(name);
  return it.hasNext() ? it.next() : folder.createFolder(name);
}

function reply(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
