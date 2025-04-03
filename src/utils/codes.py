from sqlalchemy import select, update
from .models import ActivationCode, UsedCode
from .db import safe_db_operation

async def is_code_used(code: str) -> bool:
    async def _check(session, code):
        result = await session.execute(
            select(UsedCode).where(UsedCode.code == code)
        )
        return result.scalar_one_or_none() is not None
    return await safe_db_operation(_check, code)

async def verify_activation_code(code: str, user_id: int) -> tuple[bool, str]:
    async def _verify(session, code, user_id):
        result = await session.execute(
            select(ActivationCode)
            .where(ActivationCode.code == code)
            .where(ActivationCode.is_used == False)
        )
        code_obj = result.scalar_one_or_none()
        
        if not code_obj:
            return False, ""
            
        await session.execute(
            update(ActivationCode)
            .where(ActivationCode.code == code)
            .values(
                is_used=True,
                used_at=datetime.now(),
                used_by=user_id
            )
        )
        return True, code_obj.course_id
    return await safe_db_operation(_verify, code, user_id)