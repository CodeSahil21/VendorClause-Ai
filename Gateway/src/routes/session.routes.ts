import { Router } from 'express';
import { createSession, getUserSessions, getSessionById, updateSession, deleteSession, querySession, getChatHistory } from '../controllers/session.controller';
import { validateRequest } from '../middleware/validate';
import { verifyJWT } from '../middleware/auth';
import { apiRateLimit, queryRateLimit } from '../middleware/rateLimit';
import { CreateSessionSchema, QuerySessionSchema, UpdateSessionSchema } from '../schema/session.schema';

const router = Router();

router.use(verifyJWT);
router.use(apiRateLimit); // Apply rate limiting to all session routes

router.post('/', validateRequest(CreateSessionSchema), createSession);
router.get('/', getUserSessions);
router.get('/:sessionId', getSessionById);
router.post('/:sessionId/query', queryRateLimit, validateRequest(QuerySessionSchema), querySession);
router.get('/:sessionId/messages', getChatHistory);
router.patch('/:sessionId', validateRequest(UpdateSessionSchema), updateSession);
router.delete('/:sessionId', deleteSession);

export default router;
