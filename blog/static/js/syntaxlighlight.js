import hljs from "./vendors/highlight-es6.min.mjs";

// Manually list expected languages to prevent auto-detection of the "wrong" one
hljs.configure({
  languages: ["css", "django", "js", "html", "pycon", "python"],
});

hljs.highlightAll();
