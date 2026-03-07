import bcrypt from 'bcryptjs';
import jwt, { SignOptions } from 'jsonwebtoken';
import crypto from 'crypto';
import { env } from '../config';

export const hashPassword = async (password: string): Promise<string> => {
  return await bcrypt.hash(password, 10);
};

export const comparePassword = async (password: string, hashedPassword: string): Promise<boolean> => {
  return await bcrypt.compare(password, hashedPassword);
};

export const generateToken = (userId: string, email: string, expiresIn: string = env.JWT_EXPIRES_IN): string => {
  const jti = crypto.randomUUID();
  return jwt.sign({ id: userId, email, jti }, env.JWT_SECRET, { expiresIn } as SignOptions);
};

export const generateResetToken = (): string => {
  return crypto.randomBytes(32).toString('hex');
};

/** Reset token TTL in seconds (1 hour) */
export const RESET_TOKEN_TTL = 3600;
