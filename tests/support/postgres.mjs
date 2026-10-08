import { PGlite } from '@electric-sql/pglite';
import { PGLiteSocketServer } from '@electric-sql/pglite-socket';
import { createServer } from 'node:net';
import { once } from 'node:events';
import { openDatabase, importDocuments } from '../../backend/db.mjs';

export async function database(t, seed) {
  const engine = await PGlite.create();
  const pool = {
    query: (...args) => engine.query(...args),
    connect: async () => ({ query: (...args) => engine.query(...args), release() {} }),
    end: () => engine.close(),
  };
  const db = await openDatabase('postgresql://test/test', { pool });
  t.after(async () => db.close());
  if (seed) await importDocuments(db, seed);
  return db;
}

export async function socketDatabase() {
  const probe = createServer();
  probe.listen(0, '127.0.0.1');
  await once(probe, 'listening');
  const port = probe.address().port;
  await new Promise(resolve => probe.close(resolve));
  const engine = await PGlite.create();
  const socket = new PGLiteSocketServer({ db: engine, port, host: '127.0.0.1' });
  const directPool = {
    query: (...args) => engine.query(...args),
    connect: async () => ({ query: (...args) => engine.query(...args), release() {} }),
    end: async () => {},
  };
  try {
    await socket.start();
    return { url: `postgresql://postgres@127.0.0.1:${port}/postgres`,
      directPool,
      close: async () => { await socket.stop(); await engine.close(); } };
  } catch (error) {
    await engine.close();
    throw error;
  }
}
