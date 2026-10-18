import assert from "node:assert/strict";
import test from "node:test";
import { checkModel, groupsFor, newModel, parseValue } from "../src/model.js";

const template = {
  name: "example", params: { sma_period: 50, add_percent: "25", allow_long: true },
  specs: [
    { name: "sma_period", type: "int", nullable: false },
    { name: "add_percent", type: "decimal", nullable: false },
    { name: "allow_long", type: "bool", nullable: false },
  ],
};

test("project roundtrip keeps decimal precision and independent template defaults", () => {
  const model = newModel(template);
  model.params.add_percent = "25.000000000000000000001";
  assert.deepEqual(checkModel(JSON.parse(JSON.stringify(model)), [template]), model);
  assert.equal(template.params.add_percent, "25");
  assert.equal(parseValue("25.000000000000000000001", template.specs[1]), model.params.add_percent);
  assert.deepEqual(groupsFor(template).map(group => group.key), ["signal", "restrictions", "sizing"]);
});

test("invalid imports and integer or boolean edits are rejected", () => {
  for (const value of ["", "2.5", "NaN", "9007199254740993"]) {
    assert.throws(() => parseValue(value, template.specs[0]));
  }
  assert.throws(() => parseValue("maybe", template.specs[2]));
  assert.throws(() => checkModel({ ...newModel(template), schema_version: 2 }, [template]));
  assert.throws(() => checkModel({ ...newModel(template), params: {} }, [template]));
  assert.throws(() => checkModel({ ...newModel(template), params: { ...template.params, sma_period: {} } }, [template]));
});
