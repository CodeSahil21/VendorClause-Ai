import { Request, Response } from 'express';
import jwt from 'jsonwebtoken';
import { asyncHandler } from '../utils/asyncHandler';
import { ApiResponse } from '../utils/apiResponse';
import { AuthService } from '../services/auth.service';
import { RegisterDto, LoginDto, ForgotPasswordDto, ResetPasswordDto } from '../schema/auth.schema';
import { blacklist, delSession } from '../lib/redis';
import { env } from '../config';

const COOKIE_OPTIONS = {
  httpOnly: true,
  secure: env.NODE_ENV === 'production',
  sameSite: 'strict' as const,
  maxAge: 7 * 24 * 60 * 60 * 1000 // 7 days
};

export const register = asyncHandler(async (req: Request, res: Response) => {
  const data: RegisterDto = req.body;
  const result = await AuthService.register(data);

  res.cookie('token', result.token, COOKIE_OPTIONS);

  // Only send user data in response body, not the token
  res.status(201).json(new ApiResponse(201, { user: result.user }, 'Registration successful'));
});

export const login = asyncHandler(async (req: Request, res: Response) => {
  const data: LoginDto = req.body;
  const result = await AuthService.login(data);

  res.cookie('token', result.token, COOKIE_OPTIONS);

  // Only send user data in response body, not the token
  res.status(200).json(new ApiResponse(200, { user: result.user }, 'Login successful'));
});

export const getProfile = asyncHandler(async (req: Request, res: Response) => {
  res.status(200).json(new ApiResponse(200, req.user, 'Profile retrieved'));
});

export const logout = asyncHandler(async (req: Request, res: Response) => {
  // Blacklist the current token's JTI so it can't be reused
  if (req.sessionId) {
    const token = req.cookies?.token || req.header('Authorization')?.replace('Bearer ', '');
    if (token) {
      try {
        const decoded = jwt.decode(token) as { exp?: number; jti?: string };
        if (decoded?.exp && decoded?.jti) {
          const ttl = decoded.exp - Math.floor(Date.now() / 1000);
          if (ttl > 0) {
            await Promise.all([
              blacklist(decoded.jti, ttl),
              delSession(decoded.jti)
            ]);
          }
        }
      } catch {
        // Token decode failed — still clear the cookie
      }
    }
  }

  res.clearCookie('token', {
    httpOnly: true,
    secure: env.NODE_ENV === 'production',
    sameSite: 'strict'
  });
  res.status(200).json(new ApiResponse(200, null, 'Logout successful'));
});

export const forgotPassword = asyncHandler(async (req: Request, res: Response) => {
  const data: ForgotPasswordDto = req.body;
  const result = await AuthService.forgotPassword(data);
  res.status(200).json(new ApiResponse(200, result, 'Password reset initiated'));
});

export const resetPassword = asyncHandler(async (req: Request, res: Response) => {
  const data: ResetPasswordDto = req.body;
  const result = await AuthService.resetPassword(data);
  res.status(200).json(new ApiResponse(200, result, 'Password reset successful'));
});
