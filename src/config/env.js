import dotenv from "dotenv";
dotenv.config();

export const env = {
  nodeEnv: process.env.NODE_ENV || "development",
  port: Number(process.env.PORT || 3000),
  mongoUri: process.env.MONGO_URI || "mongodb://localhost:27017/seekpal",
  jwtSecret: process.env.JWT_SECRET || "seekpal_secret_change_me",
  jwtExpiresIn: process.env.JWT_EXPIRES_IN || "24h",
  defaultPassword: process.env.DEFAULT_PASSWORD || "seekpal",
};
