// Aplica o tema escolhido antes de pintar a página (RF-CFG-04). Preferência por aparelho.
(function () {
  try {
    var t = localStorage.getItem("fin-theme");
    if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
  } catch (e) { /* armazenamento indisponível: segue o sistema */ }
})();
