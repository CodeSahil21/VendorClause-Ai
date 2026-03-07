import { Router } from 'express';
import { register, login, getProfile, logout, forgotPassword, resetPassword } from '../controllers/auth.controller';
import { validateRequest } from '../middleware/validate';
import { verifyJWT } from '../middleware/auth';
import { authRateLimit, apiRateLimit } from '../middleware/rateLimit';
import { RegisterSchema, LoginSchema, ForgotPasswordSchema, ResetPasswordSchema } from '../schema/auth.schema';

const router = Router();

// Apply rate limiting to auth routes
router.post('/register', authRateLimit, validateRequest(RegisterSchema), register);
router.post('/login', authRateLimit, validateRequest(LoginSchema), login);
router.post('/forgot-password', authRateLimit, validateRequest(ForgotPasswordSchema), forgotPassword);
router.post('/reset-password', authRateLimit, validateRequest(ResetPasswordSchema), resetPassword);

// Apply general rate limiting to protected routes
router.post('/logout', apiRateLimit, verifyJWT, logout);
router.get('/profile', apiRateLimit, verifyJWT, getProfile);

export default router;
