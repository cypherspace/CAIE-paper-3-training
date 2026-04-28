/**
 * Web App entry point. Returns the trainer HTML for embedding in Google Sites
 * (or for opening directly via the Web App URL).
 */
function doGet(e) {
  return HtmlService.createTemplateFromFile('index')
    .evaluate()
    .setTitle('CAIE Physics 9702 Paper 3 Q2 Trainer')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

/**
 * Used by index.html to inline the contents of styles.html / script.html /
 * data.html. Apps Script's HtmlService can't load multiple HTML files into a
 * single page on its own; this helper is the standard pattern.
 */
function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}
