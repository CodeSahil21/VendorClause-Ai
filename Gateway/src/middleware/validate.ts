import { Request, Response, NextFunction } from 'express';
import { TSchema } from '@sinclair/typebox';
import Ajv, { ValidateFunction } from 'ajv';
import addFormats from 'ajv-formats';
import { ApiError, ValidationError } from '../utils/apiError';

const ajv = addFormats(new Ajv({ allErrors: true }));

const validatorCache = new WeakMap<TSchema, ValidateFunction>();

const getValidator = (schema: TSchema): ValidateFunction => {
  let validate = validatorCache.get(schema);
  if (!validate) {
    validate = ajv.compile(schema);
    validatorCache.set(schema, validate);
  }
  return validate;
};

export const validateRequest = (
  schema: TSchema,
  source: 'body' | 'query' | 'params' = 'body'
) => {
  const validate = getValidator(schema);

  return (req: Request, _res: Response, next: NextFunction) => {
    const valid = validate(req[source]);

    if (!valid) {
      const errors: ValidationError[] = (validate.errors ?? []).map((err) => ({
        field: err.instancePath.replace('/', '') || (err.params as Record<string, string>)?.missingProperty,
        message: err.message,
      }));
      throw new ApiError(400, 'Validation failed', errors);
    }
    next();
  };
};
