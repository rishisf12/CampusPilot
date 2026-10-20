/*
 * Rebuilds demo/prospects.csv from demo/data.js.
 * Run:  node demo/build-csv.js
 * Add a new lead to demo/data.js, run this, then commit both files.
 */
const fs = require("fs");
const path = require("path");

global.window = {};
require(path.join(__dirname, "data.js"));

const P = window.PROSPECTS || [];
const O = window.OWNERS || {};
const Q = String.fromCharCode(34);
const q = (s) => Q + String(s == null ? "" : s).split(Q).join(Q + Q) + Q;

const head = [
  "name", "trade", "city", "state", "website", "phone", "email",
  "decision_maker", "severity", "issues", "since", "license", "address", "pitch"
];

const rows = [head.join(",")];
for (const p of P) {
  rows.push([
    p.name, p.trade, p.city, p.state, p.website, p.phone || "", p.email || "",
    O[p.id] || "", p.severity, (p.issues || []).join(" | "),
    p.since || "", p.license || "", p.address || "", p.pitch || ""
  ].map(q).join(","));
}

const out = path.join(__dirname, "prospects.csv");
fs.writeFileSync(out, rows.join("\n") + "\n");
console.log("wrote " + out + " (" + P.length + " leads)");
