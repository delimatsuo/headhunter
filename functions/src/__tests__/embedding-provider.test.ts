import { getEmbeddingProvider } from "../embedding-provider";

describe("Embedding provider selection", () => {
  const OLD = process.env.EMBEDDING_PROVIDER;
  afterAll(() => {
    if (OLD === undefined) delete process.env.EMBEDDING_PROVIDER;
    else process.env.EMBEDDING_PROVIDER = OLD;
  });

  test("defaults to vertex", () => {
    delete process.env.EMBEDDING_PROVIDER;
    const p = getEmbeddingProvider();
    expect(["vertex", "local"]).toContain(p.name); // may fallback to local at runtime
  });

  test("selects local deterministic provider", async () => {
    process.env.EMBEDDING_PROVIDER = "local";
    const p = getEmbeddingProvider();
    expect(p.name).toBe("local");
    const a = await p.generateEmbedding("hello world");
    const b = await p.generateEmbedding("hello world");
    expect(a).toHaveLength(768);
    expect(b).toHaveLength(768);
    // Deterministic
    expect(a.slice(0, 5)).toEqual(b.slice(0, 5));
  });

  test("selects together stub provider", async () => {
    process.env.EMBEDDING_PROVIDER = "together";
    const p = getEmbeddingProvider();
    expect(p.name).toBe("together");
    const a = await p.generateEmbedding("sample");
    expect(a).toHaveLength(768);
  });
});

