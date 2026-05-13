import app from "./app.js";
import { env } from "./config/env.js";
import { connectDatabase } from "./config/database.js";

connectDatabase().then(() => {
  app.listen(env.port, () => {
    console.log(`SeekPal API en http://localhost:${env.port}`);
  });
}).catch((err) => {
  console.error("Error conectando a MongoDB:", err.message);
  process.exit(1);
});
