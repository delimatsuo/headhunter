module.exports = {
  preset: "ts-jest",
  testEnvironment: "node",
  roots: ["<rootDir>/src"],
  testMatch: ["**/__tests__/**/*.ts", "**/*.(test|spec).ts"],
  setupFiles: ["<rootDir>/src/__tests__/jest.setup.ts"],
  transform: {
    "^.+\\.ts$": ["ts-jest", {
      isolatedModules: true,
      tsconfig: {
        noUnusedLocals: false,
        noUnusedParameters: false
      }
    }]
  },
  collectCoverageFrom: [
    "src/**/*.ts",
    "!src/**/*.d.ts",
    "!src/**/*.test.ts",
    "!src/**/__tests__/**",
  ],
  coverageDirectory: "coverage",
  coverageReporters: ["text", "lcov", "html"]
};