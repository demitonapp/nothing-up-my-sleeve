// Plotly's `plotly.js-dist-min` bundle ships no type declarations. The dashboard uses its `.react`,
// `.relayout`, `.purge` and `.Plots.resize` entry points, so a permissive module declaration is enough
// (the charts read their colours from the CSS tokens, not from a typed Plotly config).
declare module 'plotly.js-dist-min' {
  const Plotly: any;
  export default Plotly;
}
