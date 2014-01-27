#!/usr/sbin/dtrace -s
/*
Serial port monitor for Mac OS X.

This file is part of pyhard2 - An object-oriented framework for the
development of instrument driver.

This file only (C) 2012, Mathias Laurin, FreeBSD license.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.  Redistributions in binary
form must reproduce the above copyright notice, this list of conditions and
the following disclaimer in the documentation and/or other materials provided
with the distribution.  THIS SOFTWARE IS PROVIDED BY THE FREEBSD PROJECT ``AS
IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED.  IN NO EVENT SHALL THE FREEBSD PROJECT OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are
those of the authors and should not be interpreted as representing official
policies, either expressed or implied, of the FreeBSD Project.

*/

#pragma D option quiet

dtrace:::BEGIN
{
	printf("Logging started\n")
}

syscall::write:entry,
syscall::read:entry
/execname == "python"/
{
	self->fildes = arg0;
	self->buf    = arg1;
	self->nbyte  = arg2;
	self->offset = arg3;
}


syscall:::return
/self->fildes/
{
	self->code = errno == 0 ? "" : "Err#";
	self->text = copyin(self->buf, arg0);
	printf("%s(0x%X, \"%S\", 0x%X)\t = %d bytes [%s%d]\n", probefunc,
			self->fildes, stringof(self->text), self->nbyte,
			(int)arg0, self->code,(int)errno);	
	self->fildes = 0;
	self->buf    = 0;
	self->nbyte  = 0;
	self->offset = 0;
}

