import { Router } from 'express';
import { uploadDocument, getDocument, deleteDocument } from '../controllers/document.controller';
import { verifyJWT } from '../middleware/auth';
import { upload } from '../middleware/upload';
import { validateRequest } from '../middleware/validate';
import { uploadRateLimit, apiRateLimit } from '../middleware/rateLimit';
import { UploadDocumentSchema } from '../schema/document.schema';

const router = Router();

router.use(verifyJWT);

router.post('/upload', uploadRateLimit, upload.single('file'), validateRequest(UploadDocumentSchema), uploadDocument);
router.get('/:documentId', apiRateLimit, getDocument);
router.delete('/:documentId', apiRateLimit, deleteDocument);

export default router;
