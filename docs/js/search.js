// Filters the works on the index page as the visitor types.
// Each work carries its searchable text in data-search, already normalised by
// build.py; normalise() below must stay in step with build.py's normalise().

(function () {
  const input = document.getElementById("buscar");
  const form = input && input.form;
  const status = document.querySelector(".search-status");
  const works = Array.from(document.querySelectorAll(".work[data-search]"));
  if (!input || !form || !status || works.length === 0) return;

  function normalise(text) {
    return text
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .split(/\s+/)
      .filter(Boolean);
  }

  function apply(query) {
    const terms = normalise(query);
    let shown = 0;

    for (const work of works) {
      const text = work.dataset.search;
      const match = terms.every((term) => text.includes(term));
      work.hidden = !match;
      if (match) shown += 1;
    }

    if (terms.length === 0) {
      status.textContent = "";
    } else if (shown === 0) {
      status.textContent = `Ninguna obra coincide con «${query.trim()}».`;
    } else {
      status.textContent = shown === 1 ? "1 obra" : `${shown} obras`;
    }

    const url = new URL(window.location.href);
    if (terms.length) url.searchParams.set("q", query.trim());
    else url.searchParams.delete("q");
    window.history.replaceState(null, "", url);
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    apply(input.value);
  });
  input.addEventListener("input", () => apply(input.value));
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && input.value) {
      input.value = "";
      apply("");
    }
  });

  const initial = new URLSearchParams(window.location.search).get("q");
  if (initial) {
    input.value = initial;
    apply(initial);
  }
})();
