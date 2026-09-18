// The one assist panel with no account behind it.
//
// WHAT IT DOES AND WHAT IT CAREFULLY DOES NOT. It asks the backend to read a
// club's PUBLIC website and report what it could see. It does not verify
// anything, it does not contact the club, and it does not fill the form in on
// somebody's behalf - the reported text is shown beside the fields and every
// field stays theirs to type. A panel that auto-filled would put a model's
// reading into a nomination as though a person had checked it.
//
// WHY THE FAILURES ARE ALL QUIET BUT NOT ALL THE SAME. Three answers matter to
// the person standing here and each gets its own sentence:
//
//   503  the deployment has not switched the assistant on - the form works
//        without it and always did, so the note says so and nothing else
//        changes.
//   429  today's public budget is spent. That is a real limit on a surface
//        anybody can reach, and the honest thing is to name it rather than
//        show a spinner that never resolves.
//   anything else  it did not answer. One sentence, no retry.
//
// NO RETRY, HERE OR ANYWHERE. A retry on a paid call is a bill that grows
// while nobody is looking, and the button is right there to press again.

const API_UNSET = null;

/** Where the backend is, or null. Same seam the other two forms read. */
function apiBase() {
  const base = window.__OURHIKE_API__;
  return typeof base === "string" && base ? base.replace(/\/$/, "") : API_UNSET;
}

function main() {
  const button = document.getElementById("nominate-look");
  const website = document.getElementById("nominate-website");
  const note = document.getElementById("nominate-look-note");
  const found = document.getElementById("nominate-found");
  const foundText = document.getElementById("nominate-found-text");
  if (!button || !website || !note || !found || !foundText) return;

  button.addEventListener("click", async () => {
    const url = (website.value || "").trim();
    if (!url) {
      note.textContent = "Put their web address in first.";
      return;
    }
    const base = apiBase();
    if (base === null) {
      note.textContent =
        "The assistant is not available here. The form still works.";
      return;
    }

    button.disabled = true;
    note.textContent = "Reading their site…";
    found.hidden = true;

    let response;
    try {
      response = await fetch(`${base}/assist/nominate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ website: url }),
      });
    } catch {
      button.disabled = false;
      note.textContent = "It did not answer. The form works without it.";
      return;
    }

    button.disabled = false;

    if (response.status === 503) {
      note.textContent =
        "The assistant is not switched on here. The form still works.";
      return;
    }
    if (response.status === 429) {
      note.textContent =
        "Today's budget for this free lookup is spent. Fill the form in yourself — it is the same nomination.";
      return;
    }
    if (!response.ok) {
      note.textContent = "It did not answer. The form works without it.";
      return;
    }

    let body;
    try {
      body = await response.json();
    } catch {
      note.textContent = "Its answer could not be read.";
      return;
    }

    note.textContent = "";
    foundText.textContent = body.answer || "";
    found.hidden = false;
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", main);
} else {
  main();
}
