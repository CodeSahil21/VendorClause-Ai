import { Request, Response } from 'express';
import { asyncHandler } from '../utils/asyncHandler';
import { ApiResponse } from '../utils/apiResponse';
import { SessionService } from '../services/session.service';
import { CreateSessionDto, QuerySessionDto, UpdateSessionDto } from '../schema/session.schema';

export const createSession = asyncHandler(async (req: Request, res: Response) => {
  const data: CreateSessionDto = req.body;
  const result = await SessionService.createSession(req.user!.id, data);
  res.status(201).json(new ApiResponse(201, result, 'Session created'));
});

export const getUserSessions = asyncHandler(async (req: Request, res: Response) => {
  const page = Math.max(1, parseInt(req.query.page as string) || 1);
  const limit = Math.min(100, Math.max(1, parseInt(req.query.limit as string) || 20));

  const { sessions, total } = await SessionService.getUserSessions(req.user!.id, page, limit);
  res.status(200).json(new ApiResponse(200, {
    data: sessions,
    pagination: {
      page,
      limit,
      total,
      totalPages: Math.ceil(total / limit)
    }
  }, 'Sessions retrieved'));
});

export const getSessionById = asyncHandler(async (req: Request, res: Response) => {
  const result = await SessionService.getSessionById(req.params.sessionId as string, req.user!.id);
  res.status(200).json(new ApiResponse(200, result, 'Session retrieved'));
});

export const updateSession = asyncHandler(async (req: Request, res: Response) => {
  const data: UpdateSessionDto = req.body;
  const result = await SessionService.updateSession(req.params.sessionId as string, req.user!.id, data);
  res.status(200).json(new ApiResponse(200, result, 'Session updated'));
});

export const deleteSession = asyncHandler(async (req: Request, res: Response) => {
  await SessionService.deleteSession(req.params.sessionId as string, req.user!.id);
  res.status(200).json(new ApiResponse(200, null, 'Session deleted'));
});

export const querySession = asyncHandler(async (req: Request, res: Response) => {
  const data: QuerySessionDto = req.body;
  const result = await SessionService.dispatchQuery(req.params.sessionId as string, req.user!.id, data.question);
  res.status(202).json(new ApiResponse(202, result, 'Query queued'));
});

export const getChatHistory = asyncHandler(async (req: Request, res: Response) => {
  const limit = Math.min(100, Math.max(1, parseInt(req.query.limit as string) || 50));
  const result = await SessionService.getChatHistory(req.params.sessionId as string, req.user!.id, limit);
  res.status(200).json(new ApiResponse(200, result, 'Chat history retrieved'));
});
