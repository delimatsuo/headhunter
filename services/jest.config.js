/** @type {import('jest').Config} */
module.exports = {
  roots: ['<rootDir>/common/src', '<rootDir>/hh-search-svc/src', '<rootDir>/../tests/integration'],
  transform: {
    '^.+\\.ts$': ['ts-jest', { tsconfig: '<rootDir>/../tests/integration/tsconfig.jest.json' }]
  },
  testEnvironment: 'node',
  moduleFileExtensions: ['ts', 'js', 'json'],
  moduleNameMapper: {
    '^@hh/common(.*)$': '<rootDir>/common/src$1'
  },
  moduleDirectories: ['node_modules', '<rootDir>/node_modules', '<rootDir>/../node_modules'],
  modulePathIgnorePatterns: ['<rootDir>/../.git-rewrite'],
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js']
};
