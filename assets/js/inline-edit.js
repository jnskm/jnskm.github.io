/*
 * Inline section editor — LOCAL DEV ONLY.
 *
 * Adds an "Edit" button beside each editable section heading on a song page.
 * Editing reads/writes the raw markdown of that section via the local writer
 * (scripts/edit_server.py on 127.0.0.1:4001). Saving rewrites _music/<slug>.md;
 * Jekyll --watch rebuilds and livereload refreshes.
 *
 * Belt-and-suspenders: this file is only emitted in development, AND it refuses
 * to do anything unless served from localhost. So even if it ever shipped, it's
 * inert on jnskm.com (nothing to talk to, and it won't run).
 */
(function () {
  var host = location.hostname;
  if (host !== "localhost" && host !== "127.0.0.1") return;

  var WRITER = "http://127.0.0.1:4001/api/section";
  var EDITABLE = { "Bible Verse": 1, "Inspiration": 1, "Lyrics": 1, "Listen On": 1 };

  var article = document.querySelector("article.post[data-slug]");
  if (!article) return;
  var slug = article.getAttribute("data-slug");

  injectStyles();

  var headings = article.querySelectorAll(".post-content h1, .post-content h2, .post-content h3");
  headings.forEach(function (h) {
    var name = h.textContent.trim();
    if (!EDITABLE[name]) return;
    var btn = document.createElement("button");
    btn.className = "inline-edit-btn";
    btn.type = "button";
    btn.textContent = "Edit";
    btn.addEventListener("click", function () { openEditor(h, name); });
    h.appendChild(btn);
  });

  function sectionNodesAfter(h) {
    // Everything between this heading and the next heading (any level).
    var nodes = [];
    var n = h.nextElementSibling;
    while (n && !/^H[1-6]$/.test(n.tagName)) {
      nodes.push(n);
      n = n.nextElementSibling;
    }
    return nodes;
  }

  function openEditor(h, name) {
    if (h.dataset.editing === "1") return;
    h.dataset.editing = "1";
    var rendered = sectionNodesAfter(h);

    var box = document.createElement("div");
    box.className = "inline-edit-box";
    box.innerHTML =
      '<div class="inline-edit-status">Loading…</div>' +
      '<textarea class="inline-edit-area" spellcheck="true" disabled></textarea>' +
      '<div class="inline-edit-actions">' +
      '<button type="button" class="inline-edit-save" disabled>Save</button>' +
      '<button type="button" class="inline-edit-cancel">Cancel</button>' +
      "</div>";
    h.insertAdjacentElement("afterend", box);
    rendered.forEach(function (n) { n.style.display = "none"; });

    var area = box.querySelector(".inline-edit-area");
    var save = box.querySelector(".inline-edit-save");
    var cancel = box.querySelector(".inline-edit-cancel");
    var status = box.querySelector(".inline-edit-status");

    function close() {
      box.remove();
      rendered.forEach(function (n) { n.style.display = ""; });
      delete h.dataset.editing;
    }
    cancel.addEventListener("click", close);

    var url = WRITER + "?slug=" + encodeURIComponent(slug) + "&section=" + encodeURIComponent(name);
    fetch(url)
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
      .then(function (d) {
        area.value = d.content;
        area.disabled = false;
        save.disabled = false;
        status.textContent = "Editing “" + name + "” — saves to _music/" + slug + ".md";
        autosize(area);
        area.focus();
      })
      .catch(function (e) {
        status.textContent = "Couldn't load section (" + e + "). Is bin/serve running?";
      });

    area.addEventListener("input", function () { autosize(area); });

    save.addEventListener("click", function () {
      save.disabled = true;
      status.textContent = "Saving…";
      fetch(WRITER, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slug: slug, section: name, content: area.value }),
      })
        .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
        .then(function () {
          status.textContent = "Saved — rebuilding…";
          setTimeout(function () { location.reload(); }, 1400);
        })
        .catch(function (e) {
          status.textContent = "Save failed (" + e + ").";
          save.disabled = false;
        });
    });
  }

  function autosize(area) {
    area.style.height = "auto";
    area.style.height = area.scrollHeight + 8 + "px";
  }

  function injectStyles() {
    var css =
      ".inline-edit-btn{margin-left:.75rem;font-size:.7rem;font-family:'Courier Prime Code',monospace;" +
      "padding:.1rem .5rem;border:1px solid #ccc;border-radius:3px;background:#fff;color:#666;cursor:pointer;vertical-align:middle;}" +
      ".inline-edit-btn:hover{border-color:#c00;color:#c00;}" +
      ".inline-edit-box{margin:.5rem 0 1.5rem;padding:1rem;border:1px dashed #ccc;border-radius:4px;background:#fafafa;}" +
      ".inline-edit-status{font-family:'Courier Prime Code',monospace;font-size:.75rem;color:#888;margin-bottom:.5rem;}" +
      ".inline-edit-area{width:100%;min-height:8rem;box-sizing:border-box;font-family:'Courier Prime Code',monospace;" +
      "font-size:.9rem;line-height:1.5;padding:.75rem;border:1px solid #ddd;border-radius:3px;resize:vertical;}" +
      ".inline-edit-actions{margin-top:.6rem;display:flex;gap:.5rem;}" +
      ".inline-edit-actions button{font-family:'Courier Prime Code',monospace;font-size:.8rem;padding:.3rem .9rem;" +
      "border:1px solid #ccc;border-radius:3px;background:#fff;cursor:pointer;}" +
      ".inline-edit-save{border-color:#c00 !important;color:#c00;}" +
      ".inline-edit-save:disabled{opacity:.5;cursor:default;}";
    var s = document.createElement("style");
    s.textContent = css;
    document.head.appendChild(s);
  }
})();
