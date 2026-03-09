import { Router } from 'express';
import { verifyJWT } from '../middleware/auth';
import { apiRateLimit } from '../middleware/rateLimit';
import { getJobStatus } from '../controllers/job.controller';

const router = Router();

router.use(verifyJWT);

router.get('/:jobId', apiRateLimit, getJobStatus);

export default router;
