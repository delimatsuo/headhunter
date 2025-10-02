const createLogger = () => {
  const logger = {
    info: () => undefined,
    warn: () => undefined,
    error: () => undefined,
    child: () => logger
  };
  return logger;
};

const pino = () => createLogger();
(pino as unknown as Record<string, unknown>).default = pino;

export default pino;
