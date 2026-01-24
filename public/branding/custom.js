// Inject GLChemTec theme if OpenWebUI doesn't load custom.css automatically.
(function () {
  const id = "glc-theme-injector";
  if (document.getElementById(id)) return;

  const href = "/static/css/custom.css?v=glc1";
  const link = document.createElement("link");
  link.id = id;
  link.rel = "stylesheet";
  link.type = "text/css";
  link.href = href;
  document.head.appendChild(link);
})();
