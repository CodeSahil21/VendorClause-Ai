import nodemailer from 'nodemailer';
import { env } from '../config';

const transporter = nodemailer.createTransport({
  host: env.SMTP_HOST,
  port: env.SMTP_PORT,
  secure: env.SMTP_SECURE,
  auth: {
    user: env.SMTP_USER,
    pass: env.SMTP_PASS
  }
});

// Validate SMTP connection on startup
transporter.verify((error, success) => {
  if (error) {
    console.warn('⚠️  SMTP connection failed:', error.message);
    console.log('📝 Email functionality will be limited');
  } else {
    console.log('✅ SMTP connection verified');
  }
});

export const sendResetEmail = async (email: string, resetToken: string): Promise<void> => {
  try {
    const resetUrl = `${env.FRONTEND_URL}/reset-password?token=${resetToken}&email=${email}`;

    const mailOptions = {
      from: {
        name: 'Gateway API',
        address: env.SMTP_USER
      },
      to: email,
      subject: 'Password Reset Request',
      html: `
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
          <h2 style="color: #333;">Password Reset Request</h2>
          <p>You requested to reset your password. Click the link below to proceed:</p>
          <a href="${resetUrl}" style="display: inline-block; padding: 12px 24px; background: #2563eb; color: white; text-decoration: none; border-radius: 6px; margin: 20px 0;">Reset Password</a>
          <p style="color: #e74c3c; font-weight: bold;">⏰ This link will expire in 1 hour.</p>
          <p style="color: #666;">If you didn't request this, please ignore this email.</p>
          <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
          <p style="color: #999; font-size: 14px;">This is an automated email, please do not reply.</p>
        </div>
      `
    };

    await transporter.sendMail(mailOptions);
  } catch (error) {
    console.error('Email sending failed:', error);
    throw new Error('Failed to send reset email');
  }
};
