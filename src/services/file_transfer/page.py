"""The web page devices see: the file list, and the upload form when allowed."""

import html
from string import Template
from urllib.parse import quote


_PAGE = Template("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JasonApp File Transfer</title>
<style>
body { font: 16px -apple-system, system-ui, sans-serif; margin: 0 auto; max-width: 720px; padding: 16px; }
ul { list-style: none; padding: 0; }
li { display: flex; justify-content: space-between; gap: 12px; padding: 12px 0; border-bottom: 1px solid #8884; }
a { overflow-wrap: anywhere; }
span { color: #888; white-space: nowrap; }
section { padding: 12px; border: 1px solid #8886; border-radius: 10px; }
input, button { font: inherit; }
progress { width: 100%; }
.error { color: #d33; }
</style>
</head>
<body>
<h1>File Transfer</h1>
$upload
<ul>$rows</ul>
</body>
</html>""")


_CODE_FORM = """<section>
<form method="post" action="/unlock">
<p>$purpose</p>
<label>Code <input name="code" inputmode="numeric" autocomplete="off" maxlength="4" required></label>
<button>Unlock</button>
</form>
$message
</section>"""


_UPLOAD_FORM = """<section>
<form id="upload">
<input type="file" id="files" multiple required>
<button>Upload</button>
</form>
<progress id="progress" value="0" max="1" hidden></progress>
<p id="status"></p>
</section>
<script>
const form = document.getElementById("upload");
const progress = document.getElementById("progress");
const status = document.getElementById("status");
function send(file) {
  return new Promise(function (resolve, reject) {
    const request = new XMLHttpRequest();
    request.open("POST", "/upload?name=" + encodeURIComponent(file.name));
    request.upload.onprogress = function (event) {
      if (event.lengthComputable) progress.value = event.loaded / event.total;
    };
    request.onload = function () {
      if (request.status === 201) return resolve();
      if (request.status === 401) location.reload();
      let message = "Upload failed.";
      try { message = JSON.parse(request.responseText).error; } catch (error) {}
      reject(new Error(message));
    };
    request.onerror = function () { reject(new Error("Upload failed. Check the connection.")); };
    request.send(file);
  });
}
form.onsubmit = async function (event) {
  event.preventDefault();
  const files = Array.from(document.getElementById("files").files);
  progress.hidden = false;
  try {
    for (let index = 0; index < files.length; index++) {
      status.textContent = "Uploading " + (index + 1) + " of " + files.length + ": " + files[index].name;
      progress.value = 0;
      await send(files[index]);
    }
    location.reload();
  } catch (error) {
    progress.hidden = true;
    status.className = "error";
    status.textContent = error.message;
  }
};
</script>"""


def index_page(
    files: list[dict[str, int | str]],
    uploads_enabled: bool = False,
    code_required: bool = False,
    unlocked: bool = True,
    wrong_code: bool = False,
) -> str:
    # Without the code the list is view-only: names and sizes, no links.
    view_only = code_required and not unlocked
    rows = "".join(_row(file, view_only) for file in files) or "<li>No files are shared yet.</li>"
    if view_only:
        purpose = "Enter the code to download" + (" or upload files." if uploads_enabled else " files.")
        message = '<p class="error">That code is not right. Ask the person sharing for the code.</p>'
        section = Template(_CODE_FORM).substitute(
            purpose=purpose, message=message if wrong_code else ""
        )
    elif uploads_enabled:
        section = _UPLOAD_FORM
    else:
        section = ""
    return _PAGE.substitute(rows=rows, upload=section)


def _row(file: dict[str, int | str], view_only: bool) -> str:
    name = html.escape(str(file["name"]))
    if not view_only:
        name = f'<a href="/{quote(str(file["name"]))}" download>{name}</a>'
    return f'<li>{name}<span>{format_size(int(file["size"]))}</span></li>'


def format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"
