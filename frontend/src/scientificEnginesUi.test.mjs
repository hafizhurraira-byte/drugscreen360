import assert from "node:assert/strict";
import fs from "node:fs";

const source = fs.readFileSync(new URL("./App.jsx", import.meta.url), "utf8");
for (const required of ["Scientific Engines", "Total Engines", "Active Beta", "Licence Blocked", "Reconciliation", "Research use only", "No scientific engines match", "Loading scientific engines", "Blocked only", "Applicability domain", "No activation history"])
  assert.ok(source.includes(required), `Missing registry UI contract: ${required}`);
for (const forbidden of ["DRUGDESIGN360_REAL_DATA\\\\models", "C:\\\\Users\\\\hafiz"])
  assert.ok(!source.includes(forbidden), `Machine path leaked into UI: ${forbidden}`);
console.log("scientific engines UI tests passed");
