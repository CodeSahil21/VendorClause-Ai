import { Type, Static } from '@sinclair/typebox';

export const UploadDocumentSchema = Type.Object({
  sessionId: Type.String({ format: 'uuid' })
});

export type UploadDocumentDto = Static<typeof UploadDocumentSchema>;
