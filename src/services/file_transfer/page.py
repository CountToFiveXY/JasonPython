"""The web page devices see: a folder's contents, and the upload form when allowed."""

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
nav { color: #888; overflow-wrap: anywhere; }
</style>
</head>
<body>
$heading
$upload
<ul>$rows</ul>
</body>
</html>""")


_CODE_FORM = """<section>
<form method="post" action="/unlock">
<input type="hidden" name="next" value="$next">
<p>$purpose</p>
<label>Code <input name="code" inputmode="numeric" autocomplete="off" maxlength="4" required></label>
<button>Unlock</button>
</form>
$message
</section>"""


_UPLOAD_FORM = Template("""<section>
<form id="upload" data-folder="$folder">
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
    // Files go into the folder this page shows; folders can't be uploaded.
    request.open(
      "POST",
      "/upload?folder=" + encodeURIComponent(form.dataset.folder) +
        "&name=" + encodeURIComponent(file.name)
    );
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
</script>""")


def index_page(
    folders: list[str],
    files: list[dict[str, int | str]],
    current: list[str] | None = None,
    uploads_enabled: bool = False,
    code_required: bool = False,
    unlocked: bool = True,
    wrong_code: bool = False,
) -> str:
    """The page for one folder; current is its path, [] for the shared folder."""

    current = current or []
    # Without the code the list is view-only: folders can be browsed, but
    # files have no download links.
    view_only = code_required and not unlocked
    rows = []
    if current:
        rows.append(f'<li><a href="{folder_url(current[:-1])}">&larr; Back</a></li>')
    rows += [
        f'<li><a href="{folder_url(current + [name])}">&#128193; {html.escape(name)}</a>'
        "<span>Folder</span></li>"
        for name in folders
    ]
    rows += [_file_row(current, file, view_only) for file in files]
    if not folders and not files:
        rows.append(f"<li>{'This folder is empty.' if current else 'No files are shared yet.'}</li>")
    if view_only:
        purpose = "Enter the code to download" + (" or upload files." if uploads_enabled else " files.")
        message = '<p class="error">That code is not right. Ask the person sharing for the code.</p>'
        section = Template(_CODE_FORM).substitute(
            purpose=purpose,
            next=html.escape("/".join(current), quote=True),
            message=message if wrong_code else "",
        )
    elif uploads_enabled:
        section = _UPLOAD_FORM.substitute(folder=html.escape("/".join(current), quote=True))
    else:
        section = ""
    return _PAGE.substitute(heading=_heading(current), rows="".join(rows), upload=section)


def folder_url(parts: list[str]) -> str:
    """The page address for a folder path, such as /Photos/Trip/."""

    return "/" + "".join(quote(part) + "/" for part in parts)


def _heading(current: list[str]) -> str:
    if not current:
        return "<h1>File Transfer</h1>"
    crumbs = ['<a href="/">File Transfer</a>'] + [
        f'<a href="{folder_url(current[: index + 1])}">{html.escape(name)}</a>'
        for index, name in enumerate(current[:-1])
    ]
    return f"<nav>{' / '.join(crumbs)}</nav>\n<h1>{html.escape(current[-1])}</h1>"


def _file_row(current: list[str], file: dict[str, int | str], view_only: bool) -> str:
    name = html.escape(str(file["name"]))
    if not view_only:
        href = "/" + "/".join(quote(part) for part in current + [str(file["name"])])
        name = f'<a href="{href}" download>{name}</a>'
    return f'<li>{name}<span>{format_size(int(file["size"]))}</span></li>'


def format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"
