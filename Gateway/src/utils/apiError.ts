export interface ValidationError {
  field: string | undefined;
  message: string | undefined;
}

export class ApiError extends Error {
  statusCode: number;
  success: boolean;
  errors: ValidationError[];

  constructor(
    statusCode: number,
    message = 'Something went wrong',
    errors: ValidationError[] = []
  ) {
    super(message);
    this.statusCode = statusCode;
    this.message = message;
    this.success = false;
    this.errors = errors;

    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, this.constructor);
    }
  }
}
