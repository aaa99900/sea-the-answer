import * as sqlite from './sqlite.mjs';
import * as postgres from './postgres.mjs';

// A SQLite path is an explicit compatibility choice. Server startup normally
// passes DATABASE_URL and therefore uses PostgreSQL.
export function openDatabase(target, options = {}) {
  if (!target) throw new Error('DATABASE_URL is required. Set it to a PostgreSQL database URL in .env.');
  if (/^postgres(ql)?:\/\//i.test(target)) return postgres.openDatabase(target, options);
  return sqlite.openDatabase(target);
}

export const importDocuments = (db, input) => db.kind === 'postgres' ? postgres.importDocuments(db, input) : sqlite.importDocuments(db, input);
export const listDocuments = db => db.kind === 'postgres' ? postgres.listDocuments(db) : sqlite.listDocuments(db);
export const retrieve = (db, question, options) => db.kind === 'postgres' ? postgres.retrieve(db, question, options) : sqlite.retrieve(db, question, options);
export const saveReport = (db, input) => db.kind === 'postgres' ? postgres.saveReport(db, input) : sqlite.saveReport(db, input);
export const getReport = (db, id) => db.kind === 'postgres' ? postgres.getReport(db, id) : sqlite.getReport(db, id);
export const logTool = (db, name, input, output) => db.kind === 'postgres' ? postgres.logTool(db, name, input, output) : sqlite.logTool(db, name, input, output);
export const logQuery = (db, question, response) => db.kind === 'postgres' ? postgres.logQuery(db, question, response) : sqlite.logQuery(db, question, response);
export const countDocuments = db => db.kind === 'postgres' ? postgres.countDocuments(db) : sqlite.countDocuments(db);
