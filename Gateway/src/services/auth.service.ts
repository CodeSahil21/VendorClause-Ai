import { prisma } from '../lib/prisma';
import { ApiError } from '../utils/apiError';
import { hashPassword, comparePassword, generateToken, generateResetToken, RESET_TOKEN_TTL } from '../utils/auth';
import { RegisterDto, LoginDto, ForgotPasswordDto, ResetPasswordDto } from '../schema/auth.schema';
import { AuthResponse, ForgotPasswordResponse } from '../types/auth.types';
import { setResetToken, getResetToken, delResetToken } from '../lib/redis';
import { sendResetEmail } from '../lib/email';

export class AuthService {
  static async register(data: RegisterDto): Promise<AuthResponse> {
    const existingUser = await prisma.user.findUnique({
      where: { email: data.email }
    });

    if (existingUser) {
      throw new ApiError(400, 'Email already registered');
    }

    const passwordHash = await hashPassword(data.password);

    const user = await prisma.user.create({
      data: {
        email: data.email,
        passwordHash,
        name: data.name
      },
      select: {
        id: true,
        email: true,
        name: true,
        createdAt: true
      }
    });

    const token = generateToken(user.id, user.email);

    return { user, token };
  }

  static async login(data: LoginDto): Promise<AuthResponse> {
    const user = await prisma.user.findUnique({
      where: { email: data.email }
    });

    if (!user) {
      throw new ApiError(401, 'Invalid credentials');
    }

    const isPasswordValid = await comparePassword(data.password, user.passwordHash);

    if (!isPasswordValid) {
      throw new ApiError(401, 'Invalid credentials');
    }

    const token = generateToken(user.id, user.email);

    return {
      user: {
        id: user.id,
        email: user.email,
        name: user.name,
        createdAt: user.createdAt
      },
      token
    };
  }

  static async forgotPassword(data: ForgotPasswordDto): Promise<ForgotPasswordResponse> {
    const user = await prisma.user.findUnique({
      where: { email: data.email }
    });

    if (!user) {
      return { message: 'If email exists, reset link will be sent' };
    }

    const resetToken = generateResetToken();

    await setResetToken(user.email, resetToken, RESET_TOKEN_TTL);
    await sendResetEmail(user.email, resetToken);

    return { message: 'If email exists, reset link will be sent' };
  }

  static async resetPassword(data: ResetPasswordDto): Promise<ForgotPasswordResponse> {
    const storedToken = await getResetToken(data.email);

    if (!storedToken || storedToken !== data.token) {
      throw new ApiError(400, 'Invalid or expired reset token');
    }

    const passwordHash = await hashPassword(data.password);

    await prisma.user.update({
      where: { email: data.email },
      data: { passwordHash }
    });

    await delResetToken(data.email);

    return { message: 'Password reset successful' };
  }
}
