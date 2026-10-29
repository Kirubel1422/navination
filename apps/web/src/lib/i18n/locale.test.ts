import { describe, expect, it } from "vitest";

import { dictionaries } from "./dictionaries";
import { translate } from "./locale";

describe("dictionaries", () => {
  it("have the same keys in English and Arabic", () => {
    expect(Object.keys(dictionaries.ar).sort()).toEqual(Object.keys(dictionaries.en).sort());
  });

  it("interpolate parameters", () => {
    expect(translate("en", "stageHeading", { n: 2 })).toBe("Stage 2");
    expect(translate("ar", "stageHeading", { n: 2 })).toBe("المرحلة 2");
  });
});
