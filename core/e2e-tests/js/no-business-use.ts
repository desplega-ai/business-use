/**
 * File with no business-use imports.
 * Scanner should skip this file entirely (quick exit).
 */
import express from 'express';

const app = express();

app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

// This function happens to be called "ensure" but it's NOT from business-use
function ensure(condition: boolean, message: string) {
  if (!condition) throw new Error(message);
}

ensure(true, 'This should not be extracted');

export default app;
