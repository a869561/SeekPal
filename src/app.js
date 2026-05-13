import express from "express";
import cors from "cors";
import morgan from "morgan";
import routes from "./routes/index.js";
import { notFoundHandler, globalErrorHandler } from "./middlewares/error.middleware.js";

const app = express();

app.use(cors({ origin: "http://localhost:5173", credentials: true }));
app.use(express.json({ limit: "10mb" }));
app.use(morgan("dev"));
app.use(routes);
app.use(notFoundHandler);
app.use(globalErrorHandler);

export default app;
