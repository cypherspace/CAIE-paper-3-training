/**
 * Hydraulic Voltage — Apps Script web app entry point.
 * doGet() serves the simulator; include() inlines the *.html partials.
 */

function doGet() {
  return HtmlService.createTemplateFromFile('index')
    .evaluate()
    .setTitle('Hydraulic Voltage')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function include(name) {
  return HtmlService.createHtmlOutputFromFile(name).getContent();
}
