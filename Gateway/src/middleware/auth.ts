import { Request, Response, NextFunction } from "express";
import { asyncHandler } from "../utils/asyncHandler";
import { ApiError } from "../utils/apiError";
import jwt, { JwtPayload } from "jsonwebtoken";
import { env } from "../config";
import { prisma } from "../lib/prisma";
import { getSession, isBlacklisted, setSession } from "../lib/redis";

declare global {
  namespace Express {
    interface Request {
      user?: {
        id: string;
        email: string;
        name: string | null;
      };
      sessionId?: string;
    }
  }
}

export const verifyJWT = asyncHandler(
  async (req: Request, res: Response, next: NextFunction) => {
    const token = req.cookies?.token || req.header("Authorization")?.replace("Bearer ", "");

    if (!token) {
      throw new ApiError(401, "Unauthorized: Token not provided");
    }

    try {
      const decoded = jwt.verify(token, env.JWT_SECRET) as JwtPayload & { jti: string };

      // Check blacklist first to prevent race conditions
      const blacklisted = await isBlacklisted(decoded.jti);
      if (blacklisted) {
        throw new ApiError(401, "Unauthorized: Token has been revoked");
      }

      // Then get session data
      const sessionData = await getSession(decoded.jti);

      let userData = sessionData;
      
      if (!userData) {
        const user = await prisma.user.findUnique({
          where: { id: decoded.id },
          select: { 
            id: true, 
            email: true, 
            name: true
          }
        });

        if (!user) {
          throw new ApiError(401, "Unauthorized: User not found");
        }

        userData = {
          userId: user.id,
          email: user.email,
          name: user.name,
          lastActivity: Date.now(),
        };
        
        // Don't await - fire and forget to avoid blocking request
        setSession(decoded.jti, userData, 1800).catch(console.error);
      } else {
        // Update last activity without blocking
        userData.lastActivity = Date.now();
        setSession(decoded.jti, userData, 1800).catch(console.error);
      }

      req.user = {
        id: userData.userId,
        email: userData.email,
        name: userData.name
      };
      req.sessionId = decoded.jti;
      
      next();
    } catch (err) {
      if (err instanceof jwt.TokenExpiredError) {
        throw new ApiError(401, "TOKEN_EXPIRED");
      }
      if (err instanceof ApiError) throw err;
      throw new ApiError(401, "Unauthorized: Invalid token");
    }
  }
);
