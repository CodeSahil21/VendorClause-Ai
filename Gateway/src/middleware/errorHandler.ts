import { Request, Response, NextFunction } from 'express';
import { ApiError } from '../utils/apiError';
import { ApiResponse } from '../utils/apiResponse';
import { env } from '../config';

export const errorHandler = (
  err: Error | ApiError,
  req: Request,
  res: Response,
  next: NextFunction
) => {
  let error = err;

  if (err.name === 'JsonWebTokenError') {
    error = new ApiError(401, 'Invalid token');
  }

  const statusCode = (error as ApiError).statusCode || 500;
  const message = error.message || 'Internal Server Error';

  if (statusCode >= 500) {
    console.error(`🚨 Server Error: ${message}`, error.stack);
  }

  const errorData = {
    errors: (error as ApiError).errors || [],
    ...(env.NODE_ENV === 'development' && { stack: error.stack }),
    timestamp: new Date().toISOString(),
    path: req.path
  };

  res.status(statusCode).json(new ApiResponse(statusCode, errorData, message));
};

export const notFoundHandler = (req: Request, res: Response) => {
  const errorData = {
    timestamp: new Date().toISOString(),
    path: req.originalUrl
  };
  
  res.status(404).json(new ApiResponse(404, errorData, `Route ${req.originalUrl} not found`));
};
