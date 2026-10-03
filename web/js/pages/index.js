// Custom pages. The generic feature page (#/feature/<key>) already works for every feature;
// add a page here when a feature deserves a bespoke demo (a map, a dashboard, a wizard).
//
// Each entry: { path, title, icon, nav, render }
//   path    "#/..." route pattern, ":name" segments become params (e.g. "/building/:id")
//   icon    a name from ui.js iconNames (home, map, chart, search, file, spark, ...)
//   nav     true = show in the top bar; false = reachable by link only
//   render  async ({ params, query, config }) => Node
//
// Example (copy, then `import * as myPage from "./my_page.js"`):
//   { path: "/explore", title: "Explore", icon: "map", nav: true, render: myPage.render },
//
// `make feature NAME=x PAGE=1` writes a starter page file for you.

export const pages = [];
