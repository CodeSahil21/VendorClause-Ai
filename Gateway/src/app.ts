import express, { Application, Request, Response } from 'express';
import cors from 'cors';
import cookieParser from 'cookie-parser';
import morgan from 'morgan';
import helmet from 'helmet';
import { errorHandler, notFoundHandler } from './middleware/errorHandler';
import { ApiResponse } from './utils/apiResponse';
import { env } from './config';
import { prisma } from './lib/prisma';
import authRoutes from './routes/auth.routes';
import sessionRoutes from './routes/session.routes';
import documentRoutes from './routes/document.routes';
import jobRoutes from './routes/job.routes';

const app: Application = express();

app.use(helmet());
app.use(morgan(env.NODE_ENV === 'development' ? 'dev' : 'combined'));

app.use(cors({
  origin: [env.FRONTEND_URL, 'http://localhost:3000', 'http://localhost:3001'],
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));
app.use(cookieParser());

app.get('/', (_req: Request, res: Response) => {
  res.json(new ApiResponse(200, {
    message: 'Gateway API', 
    status: 'running',
    version: '1.0.0'
  }, 'Gateway API is running'));
});

app.get('/health', async (_req: Request, res: Response) => {
  try {
    await prisma.$queryRaw`SELECT 1`;
    res.json(new ApiResponse(200, {
      status: 'OK',
      database: 'connected',
      timestamp: new Date().toISOString()
    }, 'Health check passed'));
  } catch (error) {
    res.status(503).json(new ApiResponse(503, {
      status: 'ERROR',
      database: 'disconnected',
      timestamp: new Date().toISOString()
    }, 'Health check failed'));
  }
});

app.use('/api/v1/auth', authRoutes);
app.use('/api/v1/sessions', sessionRoutes);
app.use('/api/v1/documents', documentRoutes);
app.use('/api/v1/jobs', jobRoutes);

app.use(notFoundHandler);
app.use(errorHandler);

export default app;
