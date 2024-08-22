#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Short description.

Author:     Anna L.D. Latour
Authors:    [Anna L.D. Latour, And another one, etc]
Contact:    a.l.d.latour@tudelft.nl
Date:       2024-08-20
Maintainer: Anna L.D. Latour
Version:    0.0.1
Credits:    [One developer, And another one, etc]
Copyright:  (C) 2024, Anna L.D. Latour
License:    GPLv3
    This program is free software; you can redistribute it and/or
    modify it under the terms of the GNU General Public License
    as published by the Free Software Foundation; version 3
    of the License.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
    02110-1301, USA.
    
Description: Long description.

"""

from collections import namedtuple

Counter = namedtuple("Counter", "name path config exact",
                     defaults=[None, None, None, True])
Generator = namedtuple("Generator", "name path config",
                       defaults=[None, None, None])
Preprocessor = namedtuple("Preprocessor", "name path config",
                          defaults=[None, None, None])
DeltaDebugger = namedtuple("DeltaDebugger", "name path config",
                           defaults=[None, None, None])