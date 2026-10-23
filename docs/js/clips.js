// Plays the short silent clips on index thumbnails, but only while they are on
// screen and only when the visitor has not asked for reduced motion. Until a
// clip is actually playing, the static cover underneath stays visible.

(function () {
  const clips = Array.from(document.querySelectorAll(".work-clip"));
  if (clips.length === 0) return;

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const onScreen = new Set();

  function update(clip) {
    if (!reduceMotion.matches && onScreen.has(clip)) {
      const attempt = clip.play();
      // Autoplay can be refused (e.g. Low Power Mode); the cover then remains.
      if (attempt) attempt.catch(() => {});
    } else {
      clip.pause();
      if (reduceMotion.matches) clip.classList.remove("is-playing");
    }
  }

  for (const clip of clips) {
    clip.addEventListener("playing", () => clip.classList.add("is-playing"));
  }

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) onScreen.add(entry.target);
        else onScreen.delete(entry.target);
        update(entry.target);
      }
    },
    { rootMargin: "100px 0px" },
  );
  for (const clip of clips) observer.observe(clip);

  reduceMotion.addEventListener("change", () => clips.forEach(update));
})();
