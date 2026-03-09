import { Request, Response } from 'express';
import { asyncHandler } from '../utils/asyncHandler';
import { ApiResponse } from '../utils/apiResponse';
import { JobService } from '../services/job.service';

export const getJobStatus = asyncHandler(async (req: Request, res: Response) => {
  const result = await JobService.getJobById(req.params.jobId as string, req.user!.id);
  res.status(200).json(new ApiResponse(200, result, 'Job status retrieved'));
});
