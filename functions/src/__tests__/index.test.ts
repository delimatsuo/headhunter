import * as index from "../index";

describe("Functions exports", () => {
  test("exports enrichProfile callable with correct name", () => {
    expect(index).toHaveProperty("enrichProfile");
    // Ensure we did not accidentally export the internal helper name
    expect((index as any).enrichProfileWithGemini).toBeUndefined();
  });

  test("processUploadedProfile export exists", () => {
    expect(index).toHaveProperty("processUploadedProfile");
  });
});

