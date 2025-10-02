export default class SimpleCache<K, V> {
  private store = new Map<K, V>();

  constructor(_: Record<string, unknown> = {}) {}

  get(key: K): V | undefined {
    return this.store.get(key);
  }

  set(key: K, value: V): void {
    this.store.set(key, value);
  }

  delete(key: K): void {
    this.store.delete(key);
  }

  clear(): void {
    this.store.clear();
  }
}
