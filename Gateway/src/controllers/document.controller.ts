import { Request, Response } from 'express';
import { asyncHandler } from '../utils/asyncHandler';
import { ApiResponse } from '../utils/apiResponse';
import { DocumentService } from '../services/document.service';
import { ApiError } from '../utils/apiError';

export const uploadDocument = asyncHandler(async (req: Request, res: Response) => {
  if (!req.file) {
    throw new ApiError(400, 'No file uploaded');
  }

  // sessionId is already validated by UploadDocumentSchema in the route
  const result = await DocumentService.uploadDocument(req.user!.id, req.body.sessionId, req.file);
  res.status(202).json(new ApiResponse(202, result, 'Document queued for processing'));
});

export const getDocument = asyncHandler(async (req: Request, res: Response) => {
  const result = await DocumentService.getDocumentById(req.params.documentId as string, req.user!.id);
  res.status(200).json(new ApiResponse(200, result, 'Document retrieved'));
});

export const deleteDocument = asyncHandler(async (req: Request, res: Response) => {
  await DocumentService.deleteDocument(req.params.documentId as string, req.user!.id);
  res.status(200).json(new ApiResponse(200, null, 'Document deleted'));
});
