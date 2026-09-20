// The registration form on /for-orgs/ (features/ORG_ONBOARDING.md, #1539).
//
// THREE JOBS, AND THE FIRST ONE IS THE REASON THE OTHER TWO EXIST:
//
// 1. Show who is signed in, because **registering names you as the
//    organization's first admin.** The page renders signed-out server-side and
//    this swaps it - a static page cannot know, and guessing optimistically
//    would show a trails chair a form that cannot submit.
//
// 2. Re-evaluate the domain check LIVE, as the web address changes, as admins
//    are added and removed, and as the signed-in account changes. At least one
//    admin has to hold an email at the organization's own domain, and a check
//    that only runs on submit is a check that tells somebody they were wrong
//    after they finished typing.
//
// 3. Refuse to submit until both hold. The backend refuses too (`POST /clubs`
//    checks the VERIFIED address from the token, which is the real gate) -
//    this is the half that stops somebody filling in a long form for nothing.
//
// HOW IT KNOWS WHO IS SIGNED IN, and why it is best-effort. The app at /app/
// is the same origin as this page, and Supabase Auth persists its session in
// localStorage under `sb-<project-ref>-auth-token`. That key is read here
// rather than a Supabase client being loaded, because pulling the auth library
// into a marketing page to read one string would be a large dependency for a
// display detail. A failure of any kind - private mode, cleared storage, a key
// shape that changes - leaves the signed-out state that was already rendered,
// which is the safe direction: the worst case is somebody being asked to sign
// in when they already are, and the button next to that sentence takes them
// somewhere that works.

const SESSION_KEY = /^sb-.+-auth-token$/;

/** The signed-in address, or null. Never throws - see the header. */
function signedInEmail() {
  try {
    for (let i = 0; i < window.localStorage.length; i += 1) {
      const key = window.localStorage.key(i);
      if (!key || !SESSION_KEY.test(key)) continue;
      const raw = window.localStorage.getItem(key);
      if (!raw) continue;
      const session = JSON.parse(raw);
      const email =
        session?.user?.email ?? session?.currentSession?.user?.email;
      if (typeof email === "string" && email.includes("@"))
        return email.trim().toLowerCase();
    }
  } catch {
    // Private mode, blocked storage, or a shape this does not know. The
    // signed-out state is already on the page and is the honest fallback.
  }
  return null;
}

/** The bare domain in a web address, or ''. */
function bareDomain(value) {
  const cleaned = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, "")
    .replace(/\/.*$/, "");
  return cleaned.includes(".") ? cleaned : "";
}

/** Whether `email` sits at `domain` or a subdomain of it.
 *
 *  A subdomain counts (`trails.ramapotrails.org`) because organizations really
 *  do run mail that way, and refusing one would fail a legitimate registration
 *  with a message nobody could act on. Kept in step with the backend's own
 *  `_somebody_holds_the_domain`, which is the gate that actually decides.
 */
function atDomain(email, domain) {
  if (!domain || !email || !email.includes("@")) return false;
  const host = email.split("@").pop().trim().toLowerCase();
  return host === domain || host.endsWith("." + domain);
}

function main() {
  const form = document.getElementById("org-form");
  if (!form) return;

  const identity = document.getElementById("org-identity");
  const identityEmail = document.getElementById("org-identity-email");
  const list = document.getElementById("org-admins");
  const check = document.getElementById("org-domain-check");
  const submit = document.getElementById("org-submit");
  const website = document.getElementById("org-website");
  const addButton = document.getElementById("org-add-admin");

  const account = signedInEmail();
  if (account) {
    identity.dataset.state = "signed-in";
    identityEmail.textContent = account;
    identity.querySelector(".org-identity__in").hidden = false;
    identity.querySelector(".org-identity__out").hidden = true;
  }

  // The signed-in account is the first admin and is not removable: they are
  // the person registering, and a form that let them take themselves off would
  // be offering to register an organization on somebody else's behalf.
  const admins = [{ email: account || "", title: "", fixed: Boolean(account) }];

  function render() {
    list.replaceChildren();
    admins.forEach((admin, index) => {
      const row = document.createElement("li");
      row.className = "org-admin";

      const email = document.createElement("input");
      email.className = "org-input org-input--inline";
      email.type = "email";
      email.inputMode = "email";
      email.placeholder = "name@yourorg.org";
      email.value = admin.email;
      email.readOnly = admin.fixed;
      email.setAttribute("aria-label", `Admin ${index + 1} email address`);
      email.addEventListener("input", () => {
        admins[index].email = email.value;
        evaluate();
      });

      const title = document.createElement("input");
      title.className = "org-input org-input--inline org-input--title";
      title.type = "text";
      title.placeholder = "Trails chair";
      title.value = admin.title;
      title.setAttribute("aria-label", `Admin ${index + 1} role at the org`);
      title.addEventListener("input", () => {
        admins[index].title = title.value;
      });

      const badge = document.createElement("span");
      badge.className = "org-badge";

      row.append(email, title, badge);

      if (!admin.fixed) {
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "org-remove";
        remove.textContent = "remove";
        remove.addEventListener("click", () => {
          admins.splice(index, 1);
          render();
          evaluate();
        });
        row.append(remove);
      }

      list.append(row);
    });
    evaluate();
  }

  function evaluate() {
    const domain = bareDomain(website.value);
    const rows = list.querySelectorAll(".org-admin");
    let onDomain = 0;

    admins.forEach((admin, index) => {
      const badge = rows[index]?.querySelector(".org-badge");
      if (!badge) return;
      if (!domain || !admin.email.includes("@")) {
        badge.textContent = "";
        badge.dataset.tone = "none";
        return;
      }
      const here = atDomain(admin.email, domain);
      if (here) onDomain += 1;
      badge.textContent = here ? "org domain" : "outside domain";
      badge.dataset.tone = here ? "inside" : "outside";
    });

    const named = admins.filter((admin) => admin.email.includes("@")).length;
    let tone = "waiting";
    let message =
      "Add your web address and one admin, and we will check them against each other.";

    // THREE ANSWERS, NOT TWO, because the address you are signed in as and
    // an address you typed for a colleague are different kinds of thing.
    // The provider verified the first one. The second is a claim about
    // somebody else, and taking it as proof let anybody register any
    // organization under any domain - so the backend now accepts it and
    // HOLDS the registration rather than refusing it, and this says so
    // before the form is sent instead of after.
    const yoursIsOnDomain = atDomain(account || "", domain);
    if (domain && named) {
      if (yoursIsOnDomain) {
        tone = "ok";
        message =
          `You are signed in as ${account}, which is at ${domain}. That is the check — your ` +
          "registration goes through straight away.";
      } else if (onDomain) {
        tone = "held";
        message =
          `Nobody signed in here is at ${domain}, but you have named somebody who is. We will take ` +
          "the registration and hold it: nothing publishes, and we do not record the domain as " +
          "verified, until one of them signs in and takes their seat. An address you type for " +
          "somebody else is not something we can check.";
      } else {
        tone = "blocked";
        message =
          `None of these addresses is at ${domain}. At least one admin needs one: it is the only ` +
          "thing that shows us this organization is yours.";
      }
    }

    check.textContent = message;
    check.dataset.tone = tone;
    // Signed in, a domain, and somebody holding it. The backend checks the
    // VERIFIED address rather than any of this; the form's job is to stop
    // somebody finishing a long form that was never going to be accepted.
    submit.disabled = !(account && domain && onDomain);
  }

  website.addEventListener("input", evaluate);
  addButton.addEventListener("click", () => {
    admins.push({ email: "", title: "", fixed: false });
    render();
    const inputs = list.querySelectorAll(".org-admin .org-input");
    inputs[inputs.length - 2]?.focus();
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (submit.disabled) return;
    // The form posts nothing from this static page: the registration goes
    // through the app, which holds the signed-in session and the API base URL.
    // Carrying the typed answers across in the URL rather than asking for them
    // twice - a trails chair who retypes three admins is a trails chair who
    // stops.
    const params = new URLSearchParams({
      intent: "register-org",
      website: website.value.trim(),
      membership_url: form.elements.membership_url.value.trim(),
      donation_url: form.elements.donation_url.value.trim(),
      admins: JSON.stringify(
        admins
          .filter((admin) => admin.email.includes("@"))
          .map(({ email, title }) => ({ email, title })),
      ),
    });
    window.location.href = `/app/?${params.toString()}`;
  });

  render();
}

main();
