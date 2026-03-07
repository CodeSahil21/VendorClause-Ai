import { Type, Static } from '@sinclair/typebox';

export const RegisterSchema = Type.Object({
  email: Type.String({ format: 'email' }),
  password: Type.String({ minLength: 6, maxLength: 100 }),
  name: Type.Optional(Type.String({ minLength: 2, maxLength: 100 }))
});

export const LoginSchema = Type.Object({
  email: Type.String({ format: 'email' }),
  password: Type.String({ minLength: 6 })
});

export const ForgotPasswordSchema = Type.Object({
  email: Type.String({ format: 'email' })
});

export const ResetPasswordSchema = Type.Object({
  email: Type.String({ format: 'email' }),
  token: Type.String({ minLength: 64, maxLength: 64 }),
  password: Type.String({ minLength: 6, maxLength: 100 })
});

export type RegisterDto = Static<typeof RegisterSchema>;
export type LoginDto = Static<typeof LoginSchema>;
export type ForgotPasswordDto = Static<typeof ForgotPasswordSchema>;
export type ResetPasswordDto = Static<typeof ResetPasswordSchema>;
