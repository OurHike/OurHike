// The claim form on /for-orgs/claim/ (features/ORG_ONBOARDING.md, #1539).
//
// Two jobs, and both exist because the check that actually matters is the
// VERIFIED address on the caller's token rather than anything typed here:
//
// 1. Search the published organization list for unclaimed ones. `GET /clubs`
//    is public and returns every org that is not deleted, including the
//    unclaimed ones - which is deliberate, because an unclaimed org is exactly
//    what this page has to be able to find.
//
// 2. Show who is signed in, and enable the button only when there is somebody
//    and something. `POST /clubs/{slug}/claim` refuses on the verified address
//    regardless; this stops a trails chair finding that out after they picked
//    their org.
//
// The API base is read from the same place the app reads it, and when there is
// none - which is a normal, working deployment today, because #600 owns
// standing the backend up and nobody has - the search says so plainly rather
// than spinning. A page that spins forever is a page that looks broken; a page
// that says "this is not live yet" is a page that is telling the truth.

const SESSION_KEY = /^sb-.+-auth-token$/;

function signedInEmail() {
  try {
    for (let i = 0; i < window.localStorage.length; i += 1) {
      const key = window.localStorage.key(i);
      if (!key || !SESSION_KEY.test(key)) continue;
      const session = JSON.parse(window.localStorage.getItem(key) || "null");
      const email =
        session?.user?.email ?? session?.currentSession?.user?.email;
      if (typeof email === "string" && email.includes("@"))
        return email.trim().toLowerCase();
    }
  } catch {
    // Signed-out is already on the page and is the safe fallback.
  }
  return null;
}

/** Where the backend is, or null.
 *
 *  `window.__OURHIKE_API__` is the seam a deployment sets; there is no build
 *  step here that could bake one in, and a hardcoded host would be wrong in
 *  every environment but one.
 */
function apiBase() {
  const base = window.__OURHIKE_API__;
  return typeof base === "string" && base ? base.replace(/\/$/, "") : null;
}

function main() {
  const form = document.getElementById("claim-form");
  if (!form) return;

  const search = document.getElementById("claim-search");
  const results = document.getElementById("claim-results");
  const submit = document.getElementById("claim-submit");
  const identity = document.getElementById("claim-identity");
  const identityEmail = document.getElementById("claim-identity-email");

  const account = signedInEmail();
  if (account) {
    identity.dataset.state = "signed-in";
    identityEmail.textContent = account;
    identity.querySelector(".org-identity__in").hidden = false;
    identity.querySelector(".org-identity__out").hidden = true;
  }

  let chosen = null;
  let orgs = null;

  function enable() {
    submit.disabled = !(account && chosen);
  }

  function note(text) {
    results.replaceChildren();
    const row = document.createElement("li");
    row.className = "org-result org-result--note";
    row.textContent = text;
    results.append(row);
  }

  function render(matches) {
    results.replaceChildren();
    if (!matches.length) {
      note(
        "Nothing here by that name. If nobody has submitted it, register it yourself.",
      );
      return;
    }
    for (const org of matches) {
      const row = document.createElement("li");
      row.className = "org-result";
      row.dataset.state = org.state;

      const name = document.createElement("span");
      name.className = "org-result__name";
      name.textContent = org.name;

      const where = document.createElement("span");
      where.className = "org-result__where";
      where.textContent = org.region || org.domain || "";

      const state = document.createElement("span");
      state.className = "org-badge";
      state.dataset.tone = org.state === "unclaimed" ? "inside" : "outside";
      state.textContent = org.state === "unclaimed" ? "unclaimed" : org.state;

      row.append(name, where, state);

      if (org.state === "unclaimed") {
        const pick = document.createElement("button");
        pick.type = "button";
        pick.className = "org-add";
        pick.textContent =
          chosen?.slug === org.slug ? "chosen" : "This is mine";
        pick.addEventListener("click", () => {
          chosen = org;
          render(matches);
          enable();
        });
        row.append(pick);
      }
      results.append(row);
    }
  }

  async function load() {
    const base = apiBase();
    if (!base) {
      // #600: nothing owns standing up the production backend yet. Saying so
      // beats a spinner that never resolves.
      note(
        "The org directory is not live yet. Tell us at the link below and we will find yours by hand.",
      );
      return null;
    }
    try {
      const response = await fetch(`${base}/clubs`);
      if (!response.ok) throw new Error(String(response.status));
      return await response.json();
    } catch {
      note(
        "We could not reach the org directory just now. Try again in a minute.",
      );
      return null;
    }
  }

  search.addEventListener("input", async () => {
    const term = search.value.trim().toLowerCase();
    if (term.length < 2) {
      results.replaceChildren();
      return;
    }
    if (orgs === null) orgs = await load();
    if (!orgs) return;
    render(
      orgs.filter(
        (org) =>
          (org.name || "").toLowerCase().includes(term) ||
          (org.domain || "").toLowerCase().includes(term) ||
          (org.slug || "").toLowerCase().includes(term),
      ),
    );
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (submit.disabled || !chosen) return;
    // The claim itself goes through the app, which holds the signed-in session
    // and can send the bearer token this static page does not have.
    window.location.href = `/app/?intent=claim-org&org=${encodeURIComponent(chosen.slug)}`;
  });

  enable();
}

main();
