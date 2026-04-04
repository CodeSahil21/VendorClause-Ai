import { Type, Static } from '@sinclair/typebox';

export const CreateSessionSchema = Type.Object({
  title: Type.String({ minLength: 1, maxLength: 200 })
});

export const UpdateSessionSchema = Type.Object({
  title: Type.String({ minLength: 1, maxLength: 200 })
});

export const QuerySessionSchema = Type.Object({
  question: Type.String({ minLength: 1, maxLength: 8000 })
});

export type CreateSessionDto = Static<typeof CreateSessionSchema>;
export type UpdateSessionDto = Static<typeof UpdateSessionSchema>;
export type QuerySessionDto = Static<typeof QuerySessionSchema>;
