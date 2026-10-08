import { openDatabase as openPostgresDatabase } from './postgres.mjs';

export { importDocuments, listDocuments, retrieve, saveReport, getReport, logTool, logQuery, countDocuments } from './postgres.mjs';

export function openDatabase(connectionString, options = {}) {
  if (!/^postgres(ql)?:\/\//i.test(connectionString || '')) {
    throw new Error('DATABASE_URL must be a PostgreSQL URL (postgresql://...) in .env.');
  }
  return openPostgresDatabase(connectionString, options);
}
